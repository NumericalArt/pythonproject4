#!/usr/bin/env python3
"""
Simple Webhook Server - Trigger for script_only_send.py

This webhook server is designed to receive simple "data ready" notifications
and trigger the existing script_only_send.py processing pipeline.

Architecture:
  External Server -> Simple Webhook Signal -> script_only_send.py -> API calls -> Processing
"""

import os
import sys
import json
import time
import hmac
import hashlib
import logging
import subprocess
from datetime import datetime
from typing import Dict, Any, Tuple

from flask import Flask, request
from werkzeug.exceptions import BadRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simple_webhook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SimpleWebhookServer:
    """Simple webhook server that triggers script_only_send.py execution"""
    
    def __init__(self):
        self.app = Flask(__name__)
        self.processed_events = set()
        self.setup_routes()
        self.load_config()
    
    def load_config(self):
        self.webhook_api_key = os.getenv('WEBHOOK_API_KEY', 'api_key_for_basic_auth_change_in_production')
        self.webhook_secret_key = os.getenv('WEBHOOK_SECRET_KEY', 'webhook_secret_key_change_in_production')
        self.signature_tolerance = int(os.getenv('SIGNATURE_TOLERANCE', '300'))
        self.webhook_host = os.getenv('WEBHOOK_HOST', '0.0.0.0')
        self.webhook_port = int(os.getenv('WEBHOOK_PORT', '5001'))
        logger.info(f"Simple webhook server configured on {self.webhook_host}:{self.webhook_port}")
        logger.info("Ready to trigger script_only_send.py processing")
    
    def setup_routes(self):
        @self.app.route('/webhook', methods=['POST'])
        def webhook_endpoint():
            return self.handle_webhook_request()
        @self.app.route('/health', methods=['GET'])
        def health_check():
            return self.handle_health_check()
        @self.app.route('/status', methods=['GET'])
        def status_endpoint():
            return self.handle_status_request()
    
    def handle_webhook_request(self) -> Tuple[Dict[str, Any], int]:
        try:
            request_data = request.get_json()
            if not request_data:
                return {"error": "JSON payload required", "status": "error"}, 400
            api_key = request.headers.get('X-API-Key')
            signature = request.headers.get('X-Signature')
            timestamp_str = request.headers.get('X-Timestamp')
            event_id = request.headers.get('X-Event-ID', f"auto-{int(time.time())}")
            if not api_key:
                return {"error": "X-API-Key header required", "status": "error"}, 401
            if event_id in self.processed_events:
                return {"status": "duplicate", "message": "Event already processed", "event_id": event_id}, 409
            if api_key != self.webhook_api_key:
                return {"error": "Invalid API key", "status": "error"}, 401
            if signature and timestamp_str:
                if not self.verify_hmac_signature(signature, timestamp_str, request_data):
                    return {"error": "Invalid signature", "status": "error"}, 401
            if not self.validate_simple_payload(request_data):
                return {"error": "Invalid payload format", "status": "error"}, 400
            self.processed_events.add(event_id)
            if self.trigger_script_processing(event_id):
                return {"status": "triggered", "event_id": event_id, "triggered_at": datetime.utcnow().isoformat() + "Z"}, 200
            else:
                return {"status": "error", "message": "Failed to trigger processing", "event_id": event_id}, 500
        except BadRequest:
            return {"error": "Invalid request format", "status": "error"}, 400
        except Exception as e:
            logger.error(f"Unexpected error in webhook handler: {str(e)}")
            return {"error": "Internal server error", "status": "error"}, 500
    
    def verify_hmac_signature(self, provided_signature: str, timestamp_str: str, payload: Dict[str, Any]) -> bool:
        try:
            timestamp = int(timestamp_str)
            if abs(int(time.time()) - timestamp) > self.signature_tolerance:
                return False
            payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
            message = f"{timestamp}.{payload_str}"
            expected_signature = hmac.new(self.webhook_secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()
            expected_signature = f"sha256={expected_signature}"
            return hmac.compare_digest(provided_signature, expected_signature)
        except Exception as e:
            logger.error(f"HMAC verification error: {e}")
            return False
    
    @staticmethod
    def validate_simple_payload(payload: Dict[str, Any]) -> bool:
        return payload.get('event') == 'data_ready'
    
    def trigger_script_processing(self, event_id: str) -> bool:
        try:
            env = os.environ.copy()
            env['WEBHOOK_MODE'] = 'true'
            process = subprocess.Popen([sys.executable, 'script_only_send.py'], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.getcwd())
            time.sleep(1)
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                logger.error(f"Script failed. Stdout: {stdout.decode()} Stderr: {stderr.decode()}")
                return False
            return True
        except Exception as e:
            logger.error(f"Failed to start script_only_send.py: {e}")
            return False
    
    def handle_health_check(self):
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat() + "Z"}, 200
    
    def handle_status_request(self):
        return {"status": "running", "processed_events": len(self.processed_events)}, 200
    
    def run(self, debug: bool = False):
        self.app.run(host=self.webhook_host, port=self.webhook_port, debug=debug)

simple_webhook_server = SimpleWebhookServer()

if __name__ == '__main__':
    debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
    simple_webhook_server.run(debug=debug_mode)