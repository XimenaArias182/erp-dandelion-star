$env:Path = "$env:ProgramFiles\Git\cmd;$env:LOCALAPPDATA\Programs\Git\cmd;$env:Path"
git add -A
if (git status --porcelain) {
    git commit -m "Sincronizacion manual local <-> GitHub"
}
git pull --rebase -X ours origin main
git push origin main
