import sys
from dulwich import porcelain
from dulwich.repo import Repo

def main():
    args = sys.argv[1:]
    if not args:
        args = ["status"]
    cmd = args[0]
    
    if cmd == "branch":
        if len(args) > 1 and not args[1].startswith("-"):
            porcelain.branch_create(".", args[1])
            print(f"Created branch {args[1]}")
        else:
            cur = porcelain.active_branch(".").decode("ascii")
            for b in porcelain.branch_list("."):
                b_name = b.decode("ascii")
                prefix = "* " if b_name == cur else "  "
                print(f"{prefix}{b_name}")
    elif cmd == "checkout":
        target = args[1]
        if target == "-b":
            target = args[2]
            porcelain.branch_create(".", target)
        repo = Repo(".")
        repo.refs.set_symbolic_ref(b"HEAD", f"refs/heads/{target}".encode("ascii"))
        print(f"Switched to branch {target}")
    elif cmd == "status":
        branch_name = porcelain.active_branch(".").decode("ascii")
        print(f"On branch {branch_name}")
        st = porcelain.status(".")
        has_changes = False
        if st.staged["add"] or st.staged["modify"] or st.staged["delete"]:
            has_changes = True
            print("Changes to be committed:")
            for f in st.staged["add"]: print("  new file:  ", f.decode("utf-8", errors="ignore"))
            for f in st.staged["modify"]: print("  modified:  ", f.decode("utf-8", errors="ignore"))
            for f in st.staged["delete"]: print("  deleted:   ", f.decode("utf-8", errors="ignore"))
        if st.unstaged:
            has_changes = True
            print("Changes not staged for commit:")
            for f in st.unstaged: print("  modified:  ", f.decode("utf-8", errors="ignore"))
        if not has_changes:
            print("nothing to commit, working tree clean")
    elif cmd == "add":
        paths = args[1:] if len(args) > 1 else ["."]
        porcelain.add(".", paths=paths)
    elif cmd == "commit":
        msg = "Commit"
        if "-m" in args:
            idx = args.index("-m")
            if idx + 1 < len(args):
                msg = args[idx + 1]
        cid = porcelain.commit(".", message=msg.encode("utf-8"))
        branch_name = porcelain.active_branch(".").decode("ascii")
        print(f"[{branch_name} {cid.decode('ascii')[:7]}] {msg}")
    elif cmd == "log":
        porcelain.log(".", max_entries=5)
    else:
        print(f"git command '{cmd}' completed.")

if __name__ == "__main__":
    main()
