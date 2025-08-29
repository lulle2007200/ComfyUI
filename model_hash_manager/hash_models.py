from enum import Enum
import hashlib
import json
import os
import threading
import queue

class ModelHashType(Enum):
	SHA256 = "sha256"

class ModelHasher:
	hash_funcs = {
		ModelHashType.SHA256: hashlib.sha256
	}

	def __init__(self):
		self.job_queue = queue.Queue()
		threading.Thread(target = self.worker, daemon=True).start()

	def put(self, server, model_path, request_id, hash_type = ModelHashType.SHA256):
		self.job_queue.put((server, model_path, hash_type, request_id))

	def worker(self):
		while True:
			server, model_path, hash_type, request_id = self.job_queue.get()

			try:
				self.calculate_model_hash(server, model_path, hash_type, request_id)
			except:
				res = {
					"request_id": request_id
				}
				server.send_sync("model_hash_fail", res)
			self.job_queue.task_done()

	def calculate_model_hash(self, server, model_path: str, hash_type: ModelHashType = ModelHashType.SHA256, request_id = None):
		hash_path = os.path.join(model_path, ".hash")

		hash_data = {}
		if os.path.exists(hash_path):
			with open(hash_path, "r") as hash_file:
				try:
					hash_data = json.load(hash_file)
				except (json.JSONDecodeError, OSError):
					hash_data = {}

		model_hash = ""
		if hash_type.value in hash_data:
			model_hash = hash_data[hash_type.value]
		else:
			hasher = self.hash_funcs[hash_type]()
			with open(model_path, "rb") as model_file:
					for chunk in iter(lambda: model_file.read(0x200000), b""):
						hasher.update(chunk)

			model_hash = hasher.hexdigest()

			hash_data[hash_type.value] = model_hash

			with open(hash_path, "w") as hash_file:
				json.dump(hash_data, hash_file)

		res = {
			"request_id": request_id,
			"hash": model_hash,
		}

		server.send_sync("model_hash_complete", res)

model_hasher = ModelHasher()