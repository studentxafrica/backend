# Cron job to run the expire_offers command every day at 2 AM
#!/bin/bash
# Navigate to the project directory
cd /path/to/your/project || exit
# Activate the virtual environment if needed
# source /path/to/your/venv/bin/activate
# Run the expire_offers management command
python manage.py expire_offers
# Log the output
echo "Expired offers run at $(date)" >> /path/to/your/project/logs/expire_offers.log
# Optionally, you can redirect stderr to the log file as well
echo "Expired offers run at $(date)" >> /path/to/your/project/logs/expire_offers.log 2>&1
# Ensure the log directory exists
mkdir -p /path/to/your/project/logs
# Set appropriate permissions for the log file
chmod 644 /path/to/your/project/logs/expire_offers.log
# Exit the script
exit 0
