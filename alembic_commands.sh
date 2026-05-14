#!/usr/bin/env bash
# Alembic Migration Quick Reference
# For Lean4-Automata PostgreSQL Database

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Alembic Migration Quick Reference ===${NC}\n"

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${YELLOW}⚠ DATABASE_URL not set. Example:${NC}"
    echo "export DATABASE_URL='postgresql://lean4:lean4_dev_password@localhost:5432/lean4_automata'"
    echo ""
fi

echo -e "${GREEN}View Status:${NC}"
echo "  alembic current                    # Show current revision"
echo "  alembic history --verbose          # Show migration history"
echo "  alembic show <revision>            # Show specific migration details"
echo ""

echo -e "${GREEN}Apply Migrations:${NC}"
echo "  alembic upgrade head               # Apply all pending migrations"
echo "  alembic upgrade +1                 # Apply next migration only"
echo "  alembic upgrade 0002               # Upgrade to specific revision"
echo ""

echo -e "${GREEN}Rollback Migrations:${NC}"
echo "  alembic downgrade -1               # Rollback one migration"
echo "  alembic downgrade 0001             # Downgrade to specific revision"
echo "  alembic downgrade base             # Rollback all migrations"
echo ""

echo -e "${GREEN}Create New Migrations:${NC}"
echo "  alembic revision -m 'description'  # Create empty migration"
echo "  alembic revision --autogenerate -m 'description'  # Auto-generate from models"
echo ""

echo -e "${GREEN}Database Management:${NC}"
echo "  alembic stamp head                 # Mark DB as current without running migrations"
echo "  alembic stamp base                 # Mark DB as having no migrations"
echo ""

echo -e "${GREEN}Refresh Materialized Views (psql):${NC}"
echo "  psql \$DATABASE_URL -c 'REFRESH MATERIALIZED VIEW dependency_stats;'"
echo "  psql \$DATABASE_URL -c 'REFRESH MATERIALIZED VIEW module_metrics;'"
echo ""

echo -e "${GREEN}Verify Setup:${NC}"
echo "  # List tables"
echo "  psql \$DATABASE_URL -c '\dt'"
echo ""
echo "  # List materialized views"
echo "  psql \$DATABASE_URL -c '\dm'"
echo ""
echo "  # Check indexes"
echo "  psql \$DATABASE_URL -c '\di'"
echo ""

echo -e "${BLUE}Migration Chain:${NC}"
echo "  0001_initial_schema.py       → Enum types + core tables"
echo "  0002_add_indexes.py          → All indexes (CONCURRENTLY)"
echo "  0003_materialized_views.py   → Materialized views for metrics"
echo ""

echo -e "${YELLOW}Tip: Run 'alembic upgrade head' to apply all migrations${NC}"
