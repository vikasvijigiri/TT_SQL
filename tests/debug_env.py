import os
from dotenv import load_dotenv

# Absolute path debug
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, "../.env")
print(f"Base Dir: {base_dir}")
print(f"Env Path: {env_path}")
print(f"Env Path Exists: {os.path.exists(env_path)}")

success = load_dotenv(env_path, override=True)
print(f"load_dotenv success: {success}")

print(f"AWS_ACCESS_KEY_ID: {os.getenv('AWS_ACCESS_KEY_ID')}")
