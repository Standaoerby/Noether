# post-merge.ps1 — уборка после мержа PR (Noether). Гайка, 2026-07-10.
# Запуск из корня репо:  .\post-merge.ps1
# Делает: safety-чеки → main → fetch/pull (строго fast-forward) → удаляет ТОЛЬКО
# ветки, чьё ДЕРЕВО (содержимое) найдено в истории main — сквош-безопасный тест.
# Ветки с непоставленным содержимым НЕ трогает и громко предупреждает.
# Урок 2026-07-10: pull только на main; ветку не удалять, пока её дерево не в main.

Set-Location "C:\_PROJECTS\Noether_repo"

# 0) незавершённый merge?
if (Test-Path ".git\MERGE_HEAD") {
    Write-Host "СТОП: незавершённый merge. Сначала git merge --abort (или доведи руками)." -ForegroundColor Red
    exit 1
}

# 1) грязные tracked-файлы? (untracked — WO и пр. — не мешают)
$dirty = git status --porcelain | Where-Object { $_ -and ($_ -notmatch '^\?\?') }
if ($dirty) {
    Write-Host "СТОП: незакоммиченные правки tracked-файлов:" -ForegroundColor Red
    $dirty | ForEach-Object { Write-Host "  $_" }
    exit 1
}

# 2) на main; подтянуть строго fast-forward (мержи внутри pull запрещены)
git checkout main *> $null
git fetch --prune origin
git merge --ff-only origin/main *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "СТОП: main не обновляется fast-forward'ом — локальный main разошёлся с origin, разберись руками." -ForegroundColor Red
    exit 1
}
$mainTip = git rev-parse --short HEAD
Write-Host "main = $mainTip (== origin/main)" -ForegroundColor Green

# 3) деревья последних 100 коммитов main — база сквош-безопасного теста
$mainTrees = @(git log --format=%T -100 main)

# 4) обход локальных веток
$branches = @(git for-each-ref --format='%(refname:short)' refs/heads/ | Where-Object { $_ -ne 'main' })
if (-not $branches) { Write-Host "Локальных веток кроме main нет." }
foreach ($b in $branches) {
    $tree = git rev-parse "$b^{tree}"
    if ($mainTrees -contains $tree) {
        Write-Host "[$b] содержимое найдено в main (дерево $($tree.Substring(0,8))) — удаляю локально и на origin." -ForegroundColor Green
        git branch -D $b *> $null
        git push origin --delete $b *> $null
        if ($LASTEXITCODE -ne 0) { Write-Host "    (на origin уже удалена — ок)" -ForegroundColor DarkGray }
    } else {
        Write-Host "[$b] НЕ УДАЛЯЮ: дерево ветки НЕ найдено в main — непоставленные коммиты? Сначала PR." -ForegroundColor Yellow
        git log --oneline -3 $b | ForEach-Object { Write-Host "    $_" }
    }
}

# 5) финальный prune + краткий статус
git fetch --prune origin *> $null
git status -sb

# 6) S5 — регенерировать PROJECT_STATUS.md (один срез правды для репо и волта)
try {
    py scripts/gen_status.py
    Write-Host "PROJECT_STATUS.md обновлён." -ForegroundColor DarkGray
} catch {
    Write-Host "gen_status пропущен: $_" -ForegroundColor Yellow
}

Write-Host "Готово." -ForegroundColor Green
