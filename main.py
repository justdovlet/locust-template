import json
import os
from queue import Queue
from locust import HttpUser, between
from locust import SequentialTaskSet, task
from locust import TaskSet

# Загружаем логины и пароли из файла
with open("Files/credentials.txt", "r") as file:
    credentials = [tuple(line.strip().split(",")) for line in file.readlines()]

# Создаём очередь
credentials_queue = Queue()

# Кладём каждую пару логин-пароль внутрь
for cred in credentials:
    credentials_queue.put(cred)


# Если нужно запустить несколько Locust тестов одновременно, то надо дать им разные порты:
# locust -f locustfile.py --web-port=8089
# locust -f locustfile_2.py --web-port=8090

class BehaviorBase(TaskSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _get_headers(self):
        return {"Authorization": f'Bearer {self.user.environment.token}'}

    def _get_host(self):
        return self.user.environment.host


class YourSequentialTaskSetExample(SequentialTaskSet, BehaviorBase):
    topic_id = None

    @task
    def UC01_01_01_your_get_example(self):
        if self.user.environment.token:
            self.topic_id = None
            headers = self._get_headers()
            with self.client.get(
                    f"/api/v1/get/topics",
                    headers=headers, verify=False, catch_response=True,
                    name="UC01_01_01 /api/v1/get/topics") as response:
                if response.status_code == 200:
                    try:
                        data = response.json()
                        self.topic_id = data["topicsStat"][0]["topicId"]
                    except ValueError:
                        response.failure("JSON parsing error")
                else:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    """
    Показываю пример ответа на запрос, который отправили выше, чтобы было понятно, как его парсили:
    
    {    
        "topicsStat": [{
        "topicId": 0001,
        "topicType": {
                         "id": 1,
                         "name": "Video"
                     }},
                     {
        "topicId": 0002,
        "topicType": {
                         "id": 2,
                         "name": "Test"
                     }}]
    }
    """

    @task
    def UC01_01_02_your_post_example(self):
        if self.user.environment.token:
            headers = self._get_headers()
            headers["Content-Type"] = "application/json"
            request_data = {
                "topicId": self.topic_id,
            }
            with self.client.post(f"/api/v1/user/topic/plan", data=json.dumps(request_data), headers=headers,
                                  verify=False, catch_response=True,
                                  name="UC01_01_05 /api/v1/user/topic/plan") as response:
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get("status") != "SCHEDULED":
                            response.failure(
                                "Request for scheduling was sent, but couldn't find 'SCHEDULED' status in response")
                    except ValueError:
                        response.failure("JSON parsing error")
                else:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    """
    Ответ на запрос выше
    {
    "topic_id": "0001",
    "status": "SCHEDULED"
    }         
    """


class YourRandomTaskSetExample(BehaviorBase):

    @task(10)
    def UC01_02_01_your_task(self):
        if self.user.environment.token:
            headers = self._get_headers()
            with self.client.get(f"/YourUrl", headers=headers, verify=False, catch_response=True,
                                 name="UC01_02_01 /YourUrl") as response:
                if response.status_code != 200:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task(20)
    def UC01_02_02_your_task(self):
        if self.user.environment.token:
            headers = self._get_headers()
            with self.client.get(f"/YourUrl", headers=headers, verify=False, catch_response=True,
                                 name="UC01_02_02 /YourUrl") as response:
                if response.status_code != 200:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")


class MixedBehavior(HttpUser):
    host = "https://yourhost.com"
    wait_time = between(1, 5)

    tasks = {YourSequentialTaskSetExample: 45, YourRandomTaskSetExample: 100}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.username, self.password = None, None

    def on_start(self):
        if self.username is None:
            self.username, self.password = credentials_queue.get()
        self.environment.host = self.host
        headers = {"Content-Type": "application/json"}
        request_data = {
            "password": self.password,
            "username": self.username
        }
        with self.client.post("/api/login", data=json.dumps(request_data), headers=headers, verify=False,
                              catch_response=True, name="UC01 Login") as response:
            if response.status_code == 200:
                data = response.json()
                self.environment.token = data.get("accessToken")

    def on_stop(self):
        if self.environment.token:
            headers = {"Authorization": f'Bearer {self.environment.token}'}
            with self.client.delete("/api/logout", header=headers, headers=headers, verify=False,
                                    catch_response=True, name="UC01 Logout") as response:
                if response.status_code == 200:
                    self.environment.token = None
                    if self.username is not None:
                        credentials_queue.put((self.username, self.password))
                        self.username, self.password = None, None
