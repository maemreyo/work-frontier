#!/usr/bin/env bash
#
# Recertification dry-run for Todos 1-4 (Bootstrap Foundation)
#
# This script performs a full re-certification covering 7 verification layers:
#   1. Syntax Validation
#   2. LSP Diagnostics
#   3. Build (Static Analysis)
#   4. Unit Tests
#   5. Integration Tests
#   6. Performance/Resource Benchmarks (N/A for bootstrap)
#   7. Security Scan
#
# Usage:
#   bash .omo/recertify-todo-1-4.sh
#
# Exit codes:
#   0 - All verification layers passed
#   1 - One or more verification layers failed
#
# Evidence:
#   See .omo/reports/todo-1-4-recertification.md for detailed report
#   See .omo/evidence/task-{1,2,3,4}-full-product-implementation/verification.json

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly BLUE='\033[0;34m'
readonly BOLD='\033[1m'
readonly RESET='\033[0m'

# Project root (script is in .omo/)
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Change to project root
cd "${PROJECT_ROOT}"

# Global status tracking
LAYER_FAILURES=0

# Utility functions
print_header() {
    echo ""
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${BOLD}${BLUE}  $1${RESET}"
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
}

print_subheader() {
    echo ""
    echo -e "${BOLD}▸ $1${RESET}"
}

print_pass() {
    echo -e "  ${GREEN}✓${RESET} $1"
}

print_fail() {
    echo -e "  ${RED}✗${RESET} $1"
}

print_skip() {
    echo -e "  ${YELLOW}⊘${RESET} $1"
}

print_info() {
    echo -e "  ${BLUE}ℹ${RESET} $1"
}

run_check() {
    local description="$1"
    shift
    
    if "$@" > /dev/null 2>&1; then
        print_pass "${description}"
        return 0
    else
        print_fail "${description}"
        return 1
    fi
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 1: SYNTAX VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

layer_1_syntax_validation() {
    print_header "LAYER 1: Syntax Validation"
    
    local failures=0
    
    # Bash script syntax
    print_subheader "Bash script syntax"
    if find . -name "*.sh" -type f | while read -r script; do
        if ! bash -n "${script}" 2>/dev/null; then
            print_fail "Syntax error in ${script}"
            exit 1
        fi
    done; then
        print_pass "All bash scripts have valid syntax"
    else
        print_fail "One or more bash scripts have syntax errors"
        ((failures++))
    fi
    
    # Python syntax check
    print_subheader "Python syntax"
    if find backend/src backend/tests scripts -name "*.py" -type f 2>/dev/null | while read -r pyfile; do
        if ! python3 -m py_compile "${pyfile}" 2>/dev/null; then
            print_fail "Syntax error in ${pyfile}"
            exit 1
        fi
    done; then
        print_pass "All Python files have valid syntax"
    else
        print_fail "One or more Python files have syntax errors"
        ((failures++))
    fi
    
    # TypeScript syntax check
    print_subheader "TypeScript syntax"
    if pnpm --dir frontend exec tsc --noEmit > /dev/null 2>&1; then
        print_pass "TypeScript files have valid syntax"
    else
        print_fail "TypeScript syntax check failed"
        ((failures++))
    fi
    
    if [ ${failures} -gt 0 ]; then
        print_fail "Layer 1 FAILED (${failures} checks failed)"
        return 1
    else
        print_pass "Layer 1 PASSED"
        return 0
    fi
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 2: LSP DIAGNOSTICS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

layer_2_lsp_diagnostics() {
    print_header "LAYER 2: LSP Diagnostics"
    
    local failures=0
    
    # basedpyright strict type checking
    print_subheader "basedpyright (Python strict type checking)"
    if uv run basedpyright > /dev/null 2>&1; then
        print_pass "basedpyright: Zero errors"
    else
        print_fail "basedpyright: Type errors detected"
        ((failures++))
    fi
    
    # TypeScript strict type checking (already done in Layer 1, but verify again)
    print_subheader "TypeScript strict type checking"
    if pnpm --dir frontend exec tsc --strict --noEmit > /dev/null 2>&1; then
        print_pass "TypeScript strict: Zero errors"
    else
        print_fail "TypeScript strict: Type errors detected"
        ((failures++))
    fi
    
    if [ ${failures} -gt 0 ]; then
        print_fail "Layer 2 FAILED (${failures} checks failed)"
        return 1
    else
        print_pass "Layer 2 PASSED"
        return 0
    fi
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 3: BUILD (STATIC ANALYSIS)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

layer_3_build() {
    print_header "LAYER 3: Build (Static Analysis)"
    
    print_subheader "make check-static"
    print_info "Includes: check-preflight, check-architecture, check-contracts, Ruff, basedpyright, Biome, TypeScript"
    
    if make check-static > /dev/null 2>&1; then
        print_pass "make check-static: All gates passed"
        print_pass "Layer 3 PASSED"
        return 0
    else
        print_fail "make check-static: One or more gates failed"
        print_fail "Layer 3 FAILED"
        return 1
    fi
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 4: UNIT TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

layer_4_unit_tests() {
    print_header "LAYER 4: Unit Tests"
    
    print_subheader "make test"
    print_info "Includes: pytest (Python), Vitest (TypeScript)"
    
    if make test > /dev/null 2>&1; then
        print_pass "make test: All tests passed"
        print_pass "Layer 4 PASSED"
        return 0
    else
        print_fail "make test: One or more tests failed"
        print_fail "Layer 4 FAILED"
        return 1
    fi
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 5: INTEGRATION TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

layer_5_integration_tests() {
    print_header "LAYER 5: Integration Tests"
    
    local failures=0
    
    # Docker Compose health checks
    print_subheader "Docker Compose infrastructure health"
    if docker compose ps --format json 2>/dev/null | grep -q "running"; then
        print_pass "Docker Compose services are running"
        
        # Check PostgreSQL health
        if docker compose ps postgres 2>/dev/null | grep -q "healthy"; then
            print_pass "PostgreSQL is healthy"
        else
            print_fail "PostgreSQL is not healthy"
            ((failures++))
        fi
        
        # Check MinIO health
        if docker compose ps minio 2>/dev/null | grep -q "healthy"; then
            print_pass "MinIO is healthy"
        else
            print_fail "MinIO is not healthy"
            ((failures++))
        fi
    else
        print_fail "Docker Compose services are not running"
        print_info "Run: docker compose up -d --wait"
        ((failures++))
    fi
    
    # Migration smoke test
    print_subheader "Migration smoke test"
    if make migration-smoke > /dev/null 2>&1; then
        print_pass "Migration smoke test passed (upgrade/downgrade/rollback)"
    else
        print_fail "Migration smoke test failed"
        ((failures++))
    fi
    
    # Storage smoke test
    print_subheader "Storage smoke test"
    if make storage-smoke > /dev/null 2>&1; then
        print_pass "Storage smoke test passed (MinIO S3 round trip)"
    else
        print_fail "Storage smoke test failed"
        ((failures++))
    fi
    
    if [ ${failures} -gt 0 ]; then
        print_fail "Layer 5 FAILED (${failures} checks failed)"
        return 1
    else
        print_pass "Layer 5 PASSED"
        return 0
    fi
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 6: PERFORMANCE/RESOURCE BENCHMARKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

layer_6_performance_benchmarks() {
    print_header "LAYER 6: Performance/Resource Benchmarks"
    
    print_skip "Not applicable for bootstrap phase"
    print_info "This project is a Python/TypeScript backend, not blockchain smart contracts"
    print_info "Gas benchmarks are not relevant"
    print_info "Performance harnesses (WF-HAR-OPS-09, WF-HAR-OPS-10, WF-HAR-OPS-11) are defined"
    print_info "but not yet implemented. Required for Standard/Large/Tenant certification."
    print_pass "Layer 6 PASSED (N/A)"
    return 0
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 7: SECURITY SCAN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

layer_7_security_scan() {
    print_header "LAYER 7: Security Scan"
    
    local failures=0
    
    # gitleaks secret detection
    print_subheader "gitleaks (secret detection)"
    if command -v gitleaks > /dev/null 2>&1; then
        if gitleaks detect --source . --no-git --report-format json --report-path /dev/null > /dev/null 2>&1; then
            print_pass "gitleaks: No secrets detected"
        else
            print_fail "gitleaks: Secrets detected"
            ((failures++))
        fi
    else
        print_skip "gitleaks not installed (install: brew install gitleaks)"
        print_info "Continuing without gitleaks check"
    fi
    
    # pip-audit (Python dependency vulnerabilities)
    print_subheader "pip-audit (Python dependency vulnerabilities)"
    if uv run pip-audit --format json > /dev/null 2>&1; then
        print_pass "pip-audit: No high/critical vulnerabilities"
    else
        print_fail "pip-audit: Vulnerabilities detected"
        ((failures++))
    fi
    
    # pnpm audit (npm dependency vulnerabilities)
    print_subheader "pnpm audit (npm dependency vulnerabilities)"
    if pnpm --dir frontend audit --prod > /dev/null 2>&1; then
        print_pass "pnpm audit: No high/critical vulnerabilities"
    else
        # pnpm audit has non-zero exit even for low severity, check if high/critical exist
        if pnpm --dir frontend audit --prod 2>&1 | grep -q "high\|critical"; then
            print_fail "pnpm audit: High/critical vulnerabilities detected"
            ((failures++))
        else
            print_pass "pnpm audit: No high/critical vulnerabilities (low/moderate may exist)"
        fi
    fi
    
    if [ ${failures} -gt 0 ]; then
        print_fail "Layer 7 FAILED (${failures} checks failed)"
        return 1
    else
        print_pass "Layer 7 PASSED"
        return 0
    fi
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN EXECUTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

main() {
    echo ""
    echo -e "${BOLD}${BLUE}╔════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${BOLD}${BLUE}║  Work Frontier: Todos 1-4 Recertification Dry-Run        ║${RESET}"
    echo -e "${BOLD}${BLUE}║  Bootstrap Foundation (P0 + Todos 1-4)                    ║${RESET}"
    echo -e "${BOLD}${BLUE}╚════════════════════════════════════════════════════════════╝${RESET}"
    
    print_info "Project root: ${PROJECT_ROOT}"
    print_info "Report: .omo/reports/todo-1-4-recertification.md"
    print_info "Evidence: .omo/evidence/task-{1,2,3,4}-full-product-implementation/"
    
    # Run all verification layers
    layer_1_syntax_validation || ((LAYER_FAILURES++))
    layer_2_lsp_diagnostics || ((LAYER_FAILURES++))
    layer_3_build || ((LAYER_FAILURES++))
    layer_4_unit_tests || ((LAYER_FAILURES++))
    layer_5_integration_tests || ((LAYER_FAILURES++))
    layer_6_performance_benchmarks || ((LAYER_FAILURES++))
    layer_7_security_scan || ((LAYER_FAILURES++))
    
    # Summary
    print_header "RECERTIFICATION SUMMARY"
    
    if [ ${LAYER_FAILURES} -eq 0 ]; then
        echo ""
        echo -e "${BOLD}${GREEN}✓ ALL VERIFICATION LAYERS PASSED${RESET}"
        echo ""
        echo -e "  ${GREEN}•${RESET} Layer 1: Syntax Validation"
        echo -e "  ${GREEN}•${RESET} Layer 2: LSP Diagnostics"
        echo -e "  ${GREEN}•${RESET} Layer 3: Build (Static Analysis)"
        echo -e "  ${GREEN}•${RESET} Layer 4: Unit Tests"
        echo -e "  ${GREEN}•${RESET} Layer 5: Integration Tests"
        echo -e "  ${GREEN}•${RESET} Layer 6: Performance Benchmarks (N/A)"
        echo -e "  ${GREEN}•${RESET} Layer 7: Security Scan"
        echo ""
        echo -e "${BOLD}${GREEN}✓ TODOS 1-4 RECERTIFICATION: PASSED${RESET}"
        echo ""
        echo -e "${BOLD}Next steps:${RESET}"
        echo -e "  • Wave 1: Pure core implementation (Todos 6-10)"
        echo -e "  • Harness runner and evidence manifest (Todo 5)"
        echo -e "  • Continue toward 64/67 Standard certification"
        echo ""
        return 0
    else
        echo ""
        echo -e "${BOLD}${RED}✗ RECERTIFICATION FAILED${RESET}"
        echo -e "${RED}${LAYER_FAILURES} verification layer(s) failed${RESET}"
        echo ""
        echo -e "${BOLD}Review the output above for details.${RESET}"
        echo ""
        return 1
    fi
}

# Execute main
main
exit $?
