#!/usr/bin/env bash
# ==============================================================================
# Rucy AI Agent Termux Android Git Sync Script (Option A)
# Repository: https://github.com/hunseong-jo/Rucy.git
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}======================================================"
echo -e "     Rucy AI Termux Android Git Sync (Option A)      "
echo -e "======================================================${NC}"

# Navigate to project directory
TARGET_DIR="${HOME}/Rucy"
if [ -d "${TARGET_DIR}" ]; then
    cd "${TARGET_DIR}"
elif [ -d "$(dirname "$0")/.." ]; then
    cd "$(dirname "$0")/.."
fi

echo -e "\n${YELLOW}[1/4] Checking Git repository status in $(pwd)...${NC}"
git status -s

echo -e "\n${YELLOW}[2/4] Staging updated memories, conversations & code...${NC}"
git add .

if ! git diff --cached --quiet; then
    TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
    echo -e "${CYAN}Committing changes: 'Auto sync from Termux [${TIMESTAMP}]'${NC}"
    git commit -m "Auto sync from Termux [${TIMESTAMP}]"
else
    echo -e "${GREEN}No local changes to commit.${NC}"
fi

# Detect current branch
BRANCH=$(git branch --show-current 2>/dev/null || echo "main")

echo -e "\n${YELLOW}[3/4] Pulling updates from GitHub (${BRANCH})...${NC}"
if git pull --rebase origin "${BRANCH}" 2>/dev/null; then
    echo -e "${GREEN}✓ Successfully pulled remote updates.${NC}"
else
    echo -e "${YELLOW}! Rebase pull skipped, trying standard pull...${NC}"
    git pull origin "${BRANCH}" || true
fi

echo -e "\n${YELLOW}[4/4] Pushing updates to GitHub (${BRANCH})...${NC}"
if git push origin "${BRANCH}"; then
    echo -e "${GREEN}✓ Push completed successfully!${NC}"
else
    echo -e "${RED}❌ Push failed. Please check network connection or Git credentials.${NC}"
    exit 1
fi

echo -e "\n${GREEN}======================================================"
echo -e "     Termux Git Sync Completed Successfully!          "
echo -e "======================================================${NC}"
