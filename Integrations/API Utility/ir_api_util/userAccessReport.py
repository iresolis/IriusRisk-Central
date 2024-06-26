import os
import sys
import requests
import json
from datetime import datetime, timedelta

def read_config(config_path='config.json'):
    try:
        with open(config_path, 'r') as config_file:
            config = json.load(config_file)
            output_path = os.path.expanduser(config.get('output_path', '~/'))
            # Create the directory if it doesn't exist
            os.makedirs(output_path, exist_ok=True)
            return output_path
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading config file: {e}. Defaulting to home directory.")
        output_path = os.path.expanduser('~/')
        os.makedirs(output_path, exist_ok=True)
        return output_path

class BaseAPI:
    def __init__(self, api_token_path='~/ir/.ir_user_token', instance_domain_path='~/ir/ir_instance_domain'):
        self.api_token_path = os.path.expanduser(api_token_path)
        self.instance_domain_path = os.path.expanduser(instance_domain_path)
        self.api_token, self.instance_domain = self.read_credentials()

    def read_credentials(self):
        try:
            with open(self.api_token_path, 'r') as token_file:
                api_token = token_file.read().strip()
            with open(self.instance_domain_path, 'r') as domain_file:
                instance_domain = domain_file.read().strip()
            return api_token, instance_domain
        except FileNotFoundError as e:
            print(f"Error: {e}. Make sure the paths are correct.")
            sys.exit(1)

    def make_request(self, endpoint, params={}):
        url = f'https://{self.instance_domain}.iriusrisk.com/api/v2/{endpoint}'
        headers = {
            'Accept': 'application/hal+json',
            'api-token': self.api_token
        }
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            print(f"HTTP Error: {e.response.status_code} for URL: {e.response.url}")
            return None
        except requests.RequestException as e:
            print(f"Error: {e}")
            return None

class UserReport(BaseAPI):
    def __init__(self, api_token_path='~/ir/.ir_user_token', instance_domain_path='~/ir/ir_instance_domain'):
        super().__init__(api_token_path, instance_domain_path)
        self.output_path = read_config()

    def get_active_and_inactive_users(self, days=30):
        active_users = self.get_active_users_within_days(days)
        all_users_response = self.make_request('users')

        if not all_users_response or '_embedded' not in all_users_response:
            print("Failed to fetch users.")
            return

        all_usernames = [user['username'] for user in all_users_response['_embedded']['items']]
        active_users_set = set(active_users)
        inactive_users = list(set(all_usernames) - active_users_set)

        self.save_results(active_users, inactive_users, days)

    def get_active_users_within_days(self, days):
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_date_str = start_date.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'  # Trim microseconds

        filter_value = f"'timestamp'>='{start_date_str}':AND:'eventType'='LOGIN_SUCCESS'"
        params = {
            'filter': filter_value,
            'sort': 'timestamp'
        }

        response = self.make_request('audit-logs', params=params)

        if response and '_embedded' in response:
            active_users = [item['username'] for item in response['_embedded']['items']]
            return list(set(active_users))
        else:
            print("No active users found or error encountered.")
            return []

    def save_results(self, active_users, inactive_users, days):
        result = {
            "days": days,
            "active_users": active_users,
            "inactive_users": inactive_users
        }
        output_file = os.path.join(self.output_path, f"user_report_{days}_days.json")
        with open(output_file, 'w') as file:
            json.dump(result, file, indent=4)
        print(f"Report saved to {output_file}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 userAccessReport.py <days>")
        sys.exit(1)

    days = int(sys.argv[1])
    user_report = UserReport()
    user_report.get_active_and_inactive_users(days)

if __name__ == "__main__":
    main()
