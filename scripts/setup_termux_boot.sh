#!/usr/bin/env bash
# ==============================================================================
# Rucy AI Agent Termux:Boot Setup Script
# Configures background service auto-start upon Termux/Phone reboot.
# ==============================================================================
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}======================================================"
echo -e "     Rucy AI Termux:Boot Auto-Start Setup             "
echo -e "======================================================${NC}"

BOOT_DIR="${HOME}/.termux/boot"
mkdir -p "${BOOT_DIR}"

BOOT_SCRIPT="${BOOT_DIR}/start_lucy.sh"

echo -e "\n${YELLOW}[1/2] Writing auto-start script to ${BOOT_SCRIPT}...${NC}"

cat << 'EOF' > "${BOOT_SCRIPT}"
#!/usr/bin/env bash
# Rucy AI Boot Service Script

# Acquire wake lock to prevent phone sleeping
termux-wake-lock 2>/dev/null || true

# Find Rucy repository directory
TARGET_DIR="${HOME}/Rucy"
if [ -d "${TARGET_DIR}" ]; then
    cd "${TARGET_DIR}"
elif [ -d "$(dirname "$0")/../../my-agent" ]; then
    cd "$(dirname "$0")/../../my-agent"
elif [ -d "$(dirname "$0")/.." ]; then
    cd "$(dirname "$0")/.."
fi

# Run background git sync if script exists
if [ -f "scripts/sync_git_termux.sh" ]; then
    bash scripts/sync_git_termux.sh >/dev/null 2>&1 || true
fi

# Start Lucy agent & web background services
if command -v python >/dev/null 2>&1; then
    nohup python agent.py >/dev/null 2>&1 &
    nohup python web.py >/dev/null 2>&1 &
fi
EOF

chmod +x "${BOOT_SCRIPT}"

echo -e "\n${YELLOW}[2/2] Granting execution permissions...${NC}"
chmod +x "$0" 2>/dev/null || true

echo -e "\n${GREEN}======================================================"
echo -e "✓ Termux:Boot setup completed successfully!           "
echo -e "  Location: ${BOOT_SCRIPT}                            "
echo -e "======================================================${NC}"
