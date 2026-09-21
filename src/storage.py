"""
src/storage.py

Pluggable persistence abstraction for SDOC.
Provides an abstract interface and two implementations:
1. LocalStorage (JSON-based, dev and local fallback)
2. FirestoreStorage (Google Cloud Firestore, production Cloud Run)
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class StorageBackend(ABC):
    """Abstract interface for application persistence."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the active storage backend."""
        pass

    @abstractmethod
    def save_review_decision(self, email_id: str, decision_data: Dict[str, Any]) -> None:
        """Persist a human-in-the-loop operator decision and append to audit trail."""
        pass

    @abstractmethod
    def get_review_decisions(self) -> Dict[str, Any]:
        """Retrieve all latest operator review decisions keyed by email_id."""
        pass

    @abstractmethod
    def get_audit_trail(self, email_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve historical audit entries, optionally filtered by email_id."""
        pass

    @abstractmethod
    def save_pipeline_results(self, results: Dict[str, Any]) -> None:
        """Persist verified pipeline output."""
        pass

    @abstractmethod
    def get_pipeline_results(self) -> Optional[Dict[str, Any]]:
        """Retrieve persisted pipeline output, if any."""
        pass

    @abstractmethod
    def save_failed_processing(self, email_id: str, failure_item: Dict[str, Any]) -> None:
        """Persist a processing_failed queue item."""
        pass

    @abstractmethod
    def get_failed_processings(self) -> Dict[str, Dict[str, Any]]:
        """Retrieve all active processing_failed queue items."""
        pass

    @abstractmethod
    def remove_failed_processing(self, email_id: str) -> None:
        """Remove an item from the processing_failed queue once recovered or resolved."""
        pass

    @abstractmethod
    def test_read_write(self) -> Tuple[bool, str]:
        """Perform a live read/write roundtrip test on the storage backend."""
        pass

    @abstractmethod
    def clear_all_decisions(self) -> None:
        """Safely restore storage to initial state by clearing operator review decisions and active failures."""
        pass


class LocalStorage(StorageBackend):

    """Local JSON-file persistence for development and offline testing."""

    def __init__(self, filepath: Optional[Path] = None):
        if filepath is None:
            root = Path(__file__).resolve().parent.parent
            filepath = root / "results" / "storage_local.json"
        self.filepath = filepath
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        if not self.filepath.exists():
            self._write_state({"review_decisions": {}, "audit_trail": [], "pipeline_results": None})

    @property
    def name(self) -> str:
        return "Local JSON"

    def _read_state(self) -> Dict[str, Any]:
        try:
            if self.filepath.exists():
                return json.loads(self.filepath.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"review_decisions": {}, "audit_trail": [], "pipeline_results": None}

    def _write_state(self, state: Dict[str, Any]) -> None:
        self.filepath.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def save_review_decision(self, email_id: str, decision_data: Dict[str, Any]) -> None:
        state = self._read_state()
        data = dict(decision_data)
        now_iso = datetime.now(timezone.utc).isoformat()
        data["email_id"] = email_id
        data["updated_at"] = data.get("updated_at") or now_iso
        data["timestamp"] = data.get("timestamp") or now_iso
        data["operator"] = data.get("operator") or "human_reviewer"
        
        # 1. Update latest decision for this email
        state.setdefault("review_decisions", {})[email_id] = data
        
        # 2. Append to audit trail log
        state.setdefault("audit_trail", []).append(data)
        
        # 3. Clean from failed_processings if resolved
        if data.get("effective_status") != "processing_failed":
            if "failed_processings" in state and email_id in state["failed_processings"]:
                del state["failed_processings"][email_id]

        self._write_state(state)


    def get_review_decisions(self) -> Dict[str, Any]:
        state = self._read_state()
        return state.get("review_decisions", {})

    def get_audit_trail(self, email_id: Optional[str] = None) -> List[Dict[str, Any]]:
        state = self._read_state()
        trail = state.get("audit_trail", [])
        if email_id:
            return [t for t in trail if t.get("email_id") == email_id]
        return trail

    def save_pipeline_results(self, results: Dict[str, Any]) -> None:
        state = self._read_state()
        state["pipeline_results"] = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "data": results
        }
        self._write_state(state)

    def get_pipeline_results(self) -> Optional[Dict[str, Any]]:
        state = self._read_state()
        pkg = state.get("pipeline_results")
        return pkg.get("data") if isinstance(pkg, dict) else None

    def save_failed_processing(self, email_id: str, failure_item: Dict[str, Any]) -> None:
        state = self._read_state()
        state.setdefault("failed_processings", {})[email_id] = failure_item
        self._write_state(state)

    def get_failed_processings(self) -> Dict[str, Dict[str, Any]]:
        state = self._read_state()
        return state.get("failed_processings", {})

    def remove_failed_processing(self, email_id: str) -> None:
        state = self._read_state()
        if "failed_processings" in state and email_id in state["failed_processings"]:
            del state["failed_processings"][email_id]
            self._write_state(state)


    def test_read_write(self) -> Tuple[bool, str]:
        try:
            t0 = time.time()
            test_file = self.filepath.parent / f".disk_rw_test_{int(t0)}.tmp"
            test_file.write_text("sdoc_rw_test_ok", encoding="utf-8")
            read_back = test_file.read_text(encoding="utf-8")
            if test_file.exists():
                test_file.unlink()
            if read_back == "sdoc_rw_test_ok":
                latency_ms = int((time.time() - t0) * 1000)
                return True, f"Local disk R/W verified OK ({latency_ms}ms latency)"
            return False, "Local disk read-back content mismatch"
        except Exception as e:
            return False, f"Local disk R/W error: {e}"

    def clear_all_decisions(self) -> None:
        """Safely restore storage to initial state by clearing operator review decisions and active failures."""
        state = self._read_state()
        state["review_decisions"] = {}
        state["failed_processings"] = {}
        now_iso = datetime.now(timezone.utc).isoformat()
        state["audit_trail"] = [{
            "email_id": "SYSTEM_RESET",
            "action": "DEMO_STATE_RESET",
            "operator": "judge_demo_user",
            "timestamp": now_iso,
            "updated_at": now_iso,
            "note": "Reset demo data: Restored review queue and failures to pristine initial state."
        }]
        self._write_state(state)


class FirestoreStorage(StorageBackend):
    """Google Cloud Firestore persistence for production Cloud Run."""

    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or os.environ.get("GCP_PROJECT_ID")
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            from google.cloud import firestore
            self._client = firestore.Client(project=self.project_id)
        except Exception as e:
            self._client = None
            self._init_error = str(e)

    @property
    def name(self) -> str:
        return "Google Cloud Firestore" if self._client else "Firestore (Unavailable, Falling Back)"

    def save_review_decision(self, email_id: str, decision_data: Dict[str, Any]) -> None:
        if not self._client:
            return
        doc_data = dict(decision_data)
        now_iso = datetime.now(timezone.utc).isoformat()
        doc_data["email_id"] = email_id
        doc_data["updated_at"] = doc_data.get("updated_at") or now_iso
        doc_data["timestamp"] = doc_data.get("timestamp") or now_iso
        doc_data["operator"] = doc_data.get("operator") or "human_reviewer"
        
        # Save latest
        self._client.collection("sdoc_review_decisions").document(email_id).set(doc_data)
        # Append to audit trail subcollection
        self._client.collection("sdoc_audit_trail").add(doc_data)

    def get_review_decisions(self) -> Dict[str, Any]:
        if not self._client:
            return {}
        decisions = {}
        docs = self._client.collection("sdoc_review_decisions").stream()
        for doc in docs:
            decisions[doc.id] = doc.to_dict()
        return decisions

    def get_audit_trail(self, email_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._client:
            return []
        trail = []
        col = self._client.collection("sdoc_audit_trail")
        if email_id:
            query = col.where("email_id", "==", email_id)
            docs = query.stream()
        else:
            docs = col.stream()
        for doc in docs:
            trail.append(doc.to_dict())
        return trail

    def save_pipeline_results(self, results: Dict[str, Any]) -> None:
        if not self._client:
            return
        doc_data = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "count": len(results),
            "data": results
        }
        self._client.collection("sdoc_pipeline_results").document("latest").set(doc_data)

    def get_pipeline_results(self) -> Optional[Dict[str, Any]]:
        if not self._client:
            return None
        doc = self._client.collection("sdoc_pipeline_results").document("latest").get()
        if doc.exists:
            pkg = doc.to_dict()
            return pkg.get("data")
        return None

    def save_failed_processing(self, email_id: str, failure_item: Dict[str, Any]) -> None:
        if not self._client:
            return
        self._client.collection("sdoc_processing_failed").document(email_id).set(failure_item)

    def get_failed_processings(self) -> Dict[str, Dict[str, Any]]:
        if not self._client:
            return {}
        items = {}
        for doc in self._client.collection("sdoc_processing_failed").stream():
            items[doc.id] = doc.to_dict()
        return items

    def remove_failed_processing(self, email_id: str) -> None:
        if not self._client:
            return
        self._client.collection("sdoc_processing_failed").document(email_id).delete()

    def test_read_write(self) -> Tuple[bool, str]:

        if not self._client:
            return False, f"Firestore client not initialized: {getattr(self, '_init_error', 'No client')}"
        try:
            t0 = time.time()
            doc_ref = self._client.collection("sdoc_health_checks").document("live_test")
            doc_ref.set({"ping": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})
            snap = doc_ref.get()
            if snap.exists and snap.to_dict().get("ping") == "pong":
                doc_ref.delete()
                latency_ms = int((time.time() - t0) * 1000)
                return True, f"Firestore R/W verified OK ({latency_ms}ms latency)"
            return False, "Firestore read-back content mismatch"
        except Exception as e:
            return False, f"Firestore R/W error: {e}"

    def clear_all_decisions(self) -> None:
        """Safely restore storage to initial state by clearing operator review decisions and active failures."""
        if not self._client:
            return
        try:
            for doc in self._client.collection("sdoc_review_decisions").stream():
                doc.reference.delete()
            for doc in self._client.collection("sdoc_processing_failed").stream():
                doc.reference.delete()
        except Exception:
            pass


class GCSStorage(StorageBackend):
    """Google Cloud Storage persistence for production Cloud Run."""

    def __init__(self, bucket_name: Optional[str] = None, project_id: Optional[str] = None):
        self.bucket_name = bucket_name or os.environ.get("GCS_BUCKET_NAME", "").strip()
        self.project_id = project_id or os.environ.get("GCP_PROJECT_ID")
        self._client = None
        self._bucket = None
        self._init_error = None
        self._init_client()

    def _init_client(self):
        try:
            from google.cloud import storage
            self._client = storage.Client(project=self.project_id)
            if self.bucket_name:
                self._bucket = self._client.bucket(self.bucket_name)
        except Exception as e:
            self._client = None
            self._bucket = None
            self._init_error = str(e)

    @property
    def name(self) -> str:
        if self._bucket:
            return f"Google Cloud Storage (gs://{self.bucket_name})"
        if self.bucket_name:
            return f"GCS gs://{self.bucket_name} (Unconnected)"
        return "Google Cloud Storage (No Bucket Configured)"

    def _read_json_blob(self, blob_name: str) -> Optional[Any]:
        if not self._bucket:
            return None
        try:
            blob = self._bucket.blob(blob_name)
            if blob.exists():
                content = blob.download_as_text()
                return json.loads(content)
        except Exception:
            pass
        return None

    def _write_json_blob(self, blob_name: str, data: Any) -> bool:
        if not self._bucket:
            return False
        try:
            blob = self._bucket.blob(blob_name)
            blob.upload_from_string(json.dumps(data, indent=2), content_type="application/json")
            return True
        except Exception:
            return False

    def save_review_decision(self, email_id: str, decision_data: Dict[str, Any]) -> None:
        state = self._read_json_blob("sdoc_storage.json") or {"review_decisions": {}, "audit_trail": [], "pipeline_results": None}
        data = dict(decision_data)
        now_iso = datetime.now(timezone.utc).isoformat()
        data["email_id"] = email_id
        data["updated_at"] = data.get("updated_at") or now_iso
        data["timestamp"] = data.get("timestamp") or now_iso
        data["operator"] = data.get("operator") or "human_reviewer"
        state.setdefault("review_decisions", {})[email_id] = data
        state.setdefault("audit_trail", []).append(data)
        if data.get("effective_status") != "processing_failed":
            if "failed_processings" in state and email_id in state["failed_processings"]:
                del state["failed_processings"][email_id]
        self._write_json_blob("sdoc_storage.json", state)


    def get_review_decisions(self) -> Dict[str, Any]:
        state = self._read_json_blob("sdoc_storage.json") or {}
        return state.get("review_decisions", {})

    def get_audit_trail(self, email_id: Optional[str] = None) -> List[Dict[str, Any]]:
        state = self._read_json_blob("sdoc_storage.json") or {}
        trail = state.get("audit_trail", [])
        if email_id:
            return [t for t in trail if t.get("email_id") == email_id]
        return trail

    def save_pipeline_results(self, results: Dict[str, Any]) -> None:
        state = self._read_json_blob("sdoc_storage.json") or {"review_decisions": {}, "audit_trail": [], "pipeline_results": None}
        state["pipeline_results"] = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "data": results
        }
        self._write_json_blob("sdoc_storage.json", state)

    def get_pipeline_results(self) -> Optional[Dict[str, Any]]:
        state = self._read_json_blob("sdoc_storage.json") or {}
        pkg = state.get("pipeline_results")
        return pkg.get("data") if isinstance(pkg, dict) else None

    def save_failed_processing(self, email_id: str, failure_item: Dict[str, Any]) -> None:
        state = self._read_json_blob("sdoc_storage.json") or {"review_decisions": {}, "audit_trail": [], "pipeline_results": None, "failed_processings": {}}
        state.setdefault("failed_processings", {})[email_id] = failure_item
        self._write_json_blob("sdoc_storage.json", state)

    def get_failed_processings(self) -> Dict[str, Dict[str, Any]]:
        state = self._read_json_blob("sdoc_storage.json") or {}
        return state.get("failed_processings", {})

    def remove_failed_processing(self, email_id: str) -> None:
        state = self._read_json_blob("sdoc_storage.json") or {}
        if "failed_processings" in state and email_id in state["failed_processings"]:
            del state["failed_processings"][email_id]
            self._write_json_blob("sdoc_storage.json", state)

    def test_read_write(self) -> Tuple[bool, str]:
        """Perform a live GCS read/write roundtrip test."""
        return test_gcs_connection(self.bucket_name, project_id=self.project_id)

    def clear_all_decisions(self) -> None:
        """Safely restore storage to initial state by clearing operator review decisions and active failures."""
        state = self._read_json_blob("sdoc_storage.json") or {}
        state["review_decisions"] = {}
        state["failed_processings"] = {}
        now_iso = datetime.now(timezone.utc).isoformat()
        state["audit_trail"] = [{
            "email_id": "SYSTEM_RESET",
            "action": "DEMO_STATE_RESET",
            "operator": "judge_demo_user",
            "timestamp": now_iso,
            "updated_at": now_iso,
            "note": "Reset demo data: Restored review queue and failures to pristine initial state."
        }]
        self._write_json_blob("sdoc_storage.json", state)


def reset_demo_data() -> bool:
    """Convenience helper to safely restore active storage backend to initial demo state."""
    storage = get_storage()
    if hasattr(storage, "clear_all_decisions"):
        storage.clear_all_decisions()
        return True
    return False



def test_gcs_connection(bucket_name: Optional[str] = None, project_id: Optional[str] = None) -> Tuple[bool, str]:
    """Standalone live GCS read/write verification test."""
    bucket_str = (bucket_name or os.environ.get("GCS_BUCKET_NAME", "")).strip()
    if not bucket_str:
        return False, "GCS_BUCKET_NAME environment variable is not configured."

    try:
        from google.cloud import storage
    except ImportError:
        return False, "google-cloud-storage package is not installed."

    try:
        client = storage.Client(project=project_id or os.environ.get("GCP_PROJECT_ID"))
        bucket = client.bucket(bucket_str)
        t0 = time.time()
        test_blob_name = f"_sdoc_health_rw_test_{int(t0)}.txt"
        blob = bucket.blob(test_blob_name)
        test_content = f"sdoc_gcs_ping_{t0}"
        blob.upload_from_string(test_content, content_type="text/plain")
        read_back = blob.download_as_text()
        blob.delete()
        if read_back == test_content:
            latency_ms = int((time.time() - t0) * 1000)
            return True, f"GCS R/W verified on gs://{bucket_str} ({latency_ms}ms latency)"
        return False, "GCS read-back content mismatch"
    except Exception as e:
        return False, f"GCS test failed: {e}"


def get_storage() -> StorageBackend:
    """Factory returning configured storage backend based on STORAGE_BACKEND env var."""
    backend_choice = os.environ.get("STORAGE_BACKEND", "local").strip().lower()
    
    if backend_choice in ("gcs", "google_cloud_storage"):
        gcs = GCSStorage()
        if gcs._bucket is not None:
            return gcs
        return gcs
    
    if backend_choice == "firestore":
        fs = FirestoreStorage()
        if fs._client is not None:
            return fs
        return LocalStorage()
    
    return LocalStorage()
