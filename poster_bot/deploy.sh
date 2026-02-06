#!/bin/bash

# ===========================================
# Poster Bot Deploy Script
# ===========================================
# Usage:
#   ./deploy.sh          - Push to production (auto-deploy)
#   ./deploy.sh setup    - Initial server setup
#   ./deploy.sh logs     - View backend logs
#   ./deploy.sh status   - Check service status
#   ./deploy.sh restart  - Restart backend
# ===========================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SERVER="poster-dev"
REMOTE_PATH="/var/www/poster-bot"
DOMAIN="lgzt.developing-site.ru"

# Functions
print_step() {
    echo -e "${BLUE}[$1]${NC} $2"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

# Commands
case "${1:-deploy}" in
    setup)
        echo ""
        echo "==========================================="
        echo "   Poster Bot - Initial Server Setup"
        echo "==========================================="
        echo ""

        print_step 1 "Creating directories on server..."
        ssh $SERVER "mkdir -p $REMOTE_PATH/backend/data/sessions $REMOTE_PATH/backend/data/uploads $REMOTE_PATH/frontend/dist /var/log/poster-bot"

        print_step 2 "Setting up bare git repo..."
        ssh $SERVER "mkdir -p $REMOTE_PATH.git && cd $REMOTE_PATH.git && git init --bare"

        print_step 3 "Uploading post-receive hook..."
        scp ./server/post-receive $SERVER:$REMOTE_PATH.git/hooks/
        ssh $SERVER "chmod +x $REMOTE_PATH.git/hooks/post-receive"

        print_step 4 "Setting up Python environment..."
        ssh $SERVER "cd $REMOTE_PATH/backend && python3 -m venv venv"

        print_step 5 "Installing certbot if needed..."
        ssh $SERVER "which certbot || apt install -y certbot python3-certbot-nginx"

        print_step 6 "Adding git remote locally..."
        git remote remove production 2>/dev/null || true
        git remote add production $SERVER:$REMOTE_PATH.git

        print_success "Setup complete!"
        echo ""
        echo "Next steps:"
        echo "  1. Run: ./deploy.sh"
        echo "  2. Get SSL: ssh $SERVER 'certbot --nginx -d $DOMAIN'"
        echo ""
        ;;

    logs)
        echo "Showing backend logs..."
        ssh $SERVER "journalctl -u poster-bot -f"
        ;;

    deploy-log)
        echo "Showing deploy log..."
        ssh $SERVER "tail -100 /var/log/poster-bot/deploy.log"
        ;;

    status)
        echo "Service status:"
        ssh $SERVER "systemctl status poster-bot --no-pager" || true
        echo ""
        echo "Recent deploy log:"
        ssh $SERVER "tail -20 /var/log/poster-bot/deploy.log" || true
        ;;

    restart)
        echo "Restarting backend..."
        ssh $SERVER "systemctl restart poster-bot"
        print_success "Backend restarted"
        ;;

    ssl)
        echo "Getting SSL certificate..."
        ssh $SERVER "certbot --nginx -d $DOMAIN"
        print_success "SSL configured"
        ;;

    deploy|*)
        echo ""
        echo "==========================================="
        echo "   Poster Bot Deployment"
        echo "==========================================="
        echo ""
        echo "Target: production"
        echo "Server: $SERVER"
        echo "Domain: $DOMAIN"
        echo ""

        # Check for changes
        if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
            print_step 1 "Uncommitted changes detected"
            echo ""
            git status --short
            echo ""
            read -p "Commit message (or 'skip' to deploy without commit): " commit_msg

            if [ "$commit_msg" != "skip" ] && [ -n "$commit_msg" ]; then
                git add .
                git commit -m "$commit_msg"
                print_success "Changes committed"
            fi
        else
            print_step 1 "No uncommitted changes"
        fi

        # Push to production
        print_step 2 "Pushing to production..."

        if git push production master 2>&1; then
            print_success "Pushed to production"
        elif git push production main 2>&1; then
            print_success "Pushed to production (main branch)"
        else
            print_error "Failed to push. Run setup first:"
            echo "  ./deploy.sh setup"
            exit 1
        fi

        # Wait for deploy
        print_step 3 "Waiting for deployment..."
        sleep 5

        # Check status
        print_step 4 "Checking deployment..."

        status_code=$(curl -s -o /dev/null -w "%{http_code}" "http://$DOMAIN/" 2>/dev/null || echo "000")
        api_status=$(curl -s -o /dev/null -w "%{http_code}" "http://$DOMAIN/api/stats" 2>/dev/null || echo "000")

        echo ""
        if [ "$status_code" == "200" ]; then
            print_success "Frontend: OK (HTTP $status_code)"
        else
            print_warning "Frontend: HTTP $status_code"
        fi

        if [ "$api_status" == "401" ] || [ "$api_status" == "200" ]; then
            print_success "Backend API: OK (HTTP $api_status)"
        else
            print_warning "Backend API: HTTP $api_status"
        fi

        echo ""
        echo "==========================================="
        echo -e "${GREEN}Deployment complete!${NC}"
        echo "==========================================="
        echo ""
        echo "Site: http://$DOMAIN/"
        echo ""
        echo "Commands:"
        echo "  ./deploy.sh logs     - View logs"
        echo "  ./deploy.sh status   - Check status"
        echo "  ./deploy.sh ssl      - Get SSL certificate"
        echo ""
        ;;
esac
