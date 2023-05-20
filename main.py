import json
import os
from queue import Queue
from locust import HttpUser, between
from locust import SequentialTaskSet, task
from locust import TaskSet

# Loading credentials from file
with open("Files/credentials.txt", "r") as file:
    credentials = [tuple(line.strip().split(",")) for line in file.readlines()]

# Creating queue and putting each credential inside
credentials_queue = Queue()
for cred in credentials:
    credentials_queue.put(cred)


# To run multiple instances of Locust at once we should use different ports:
# locust -f locustfile.py --web-port=8089
# locust -f locustfile.py --web-port=8090


class BehaviorBase(TaskSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _get_headers(self):
        return {"Authorization": f'Bearer {self.user.environment.token}'}

    def _get_host(self):
        return self.user.environment.host


class ScormTaskSequence(SequentialTaskSet, BehaviorBase):
    user_id = None
    topic_id = None
    block_id = None
    scorm_id = None
    plan_id = None

    @task
    def UC01_01_01_get_home_page(self):
        if self.user.environment.token:
            self.user_id = None
            headers = self._get_headers()
            with self.client.get("/collection-topics", headers=headers, verify=False, catch_response=True,
                                 name="UC01_01_01 /collection-topics") as response:
                if response.status_code != 200 and response.status_code != 304:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task
    def UC01_01_02_get_user_id(self):
        if self.user.environment.token:
            self.user_id = None
            headers = self._get_headers()
            with self.client.get("/api/v1/user", headers=headers, verify=False, catch_response=True,
                                 name="UC01_01_02 /api/v1/user") as response:
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get("id") is not None:
                            self.user_id = data.get("id")
                        else:
                            response.failure("Can't find user id in response")
                    except ValueError:
                        response.failure("JSON parsing error")
                else:
                    response.failure(f"Unexpected status code:  {response.status_code}")

    @task
    def UC01_01_03_get_topic_id(self):
        if self.user.environment.token:
            self.topic_id = None
            headers = self._get_headers()
            with self.client.get(
                    "/api/v1/topic?size=19&sort=positions.position,asc&sort=createdDate,desc&sort=id,"
                    "asc&status=ACTIVE&isPersonalized=true",
                    headers=headers, verify=False, catch_response=True, name="UC01_01_03 /api/v1/topic") as response:
                if response.status_code == 200:
                    try:
                        data = response.json()

                        # In for-loop searches for the first topic that has LoadTest_Scorm name. All topics were created
                        # with specific name for this operation. Topic also should NOT have planned status to be picked.
                        for item in data:
                            if item["name"] == "LoadTest_Scorm" and item["planStatus"]["planStatus"] is None:
                                self.topic_id = item["id"]
                                break
                        if self.topic_id is None:
                            response.failure("No matching element found")
                    except ValueError:
                        response.failure("JSON parsing error")
                else:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task
    def UC01_01_04_get_topic_by_id(self):
        if self.user.environment.token:
            headers = self._get_headers()
            with self.client.get(f"/collection-topics/{self.topic_id}", headers=headers, verify=False,
                                 catch_response=True, name="UC01_01_04 /collection-topics/{topic_id}") as response:
                if response.status_code != 200:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task
    def UC01_01_05_schedule_topic(self):
        if self.user.environment.token:
            headers = self._get_headers()
            headers["Content-Type"] = "application/json"
            request_data = {
                "comment": "",
                "date": "2023-12-31",
                "topicId": self.topic_id,
                "userId": self.user_id
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

    @task
    def UC01_01_06_get_block_id(self):
        if self.user.environment.token:
            self.block_id = None
            self.scorm_id = None
            headers = self._get_headers()
            with self.client.get(
                    f"/api/v1/block/result/statistic?topicId={self.topic_id}&userId={self.user_id}",
                    headers=headers, verify=False, catch_response=True,
                    name="UC01_01_06 /api/v1/block/result/statistic") as response:
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data["countBlocks"] == 1:
                            self.block_id = data["blocksStat"][0]["blockId"]
                            self.scorm_id = data["blocksStat"][0]["scorm"]["scormId"]
                        else:
                            response.failure(f"Found {data['countBlocks']}, expected 1 block in topic {self.topic_id}")
                    except ValueError:
                        response.failure("JSON parsing error")
                else:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task
    def UC01_01_07_get_scorm(self):
        if self.user.environment.token:
            headers = self._get_headers()
            with self.client.get(f"/api/v1/scorm/{self.scorm_id}", headers=headers, verify=False,
                                 catch_response=True, name="UC01_01_07 /api/v1/scorm/{scorm_id}") as response:
                if response.status_code != 200:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task
    def UC01_01_08_finish_scorm(self):
        if self.user.environment.token:
            headers = self._get_headers()
            with self.client.put(f"/api/v1/block/{self.block_id}/scorm/finish", headers=headers,
                                 verify=False, catch_response=True,
                                 name="UC01_01_08 /api/v1/block/{self.block_id}/scorm/finish") as response:
                if response.status_code != 200:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task
    def UC01_01_09_get_plan_id(self):
        if self.user.environment.token:
            self.plan_id = None
            headers = self._get_headers()
            with self.client.get(f"/api/v1/user/topic/plan?topicId={self.topic_id}&userId={self.user_id}",
                                 headers=headers,
                                 verify=False, catch_response=True,
                                 name="UC01_01_09 /api/v1/user/topic/plan") as response:
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if "id" not in data[0]:
                            response.failure(f"Can't find id in response data")
                        else:
                            self.plan_id = data[0]["id"]
                    except ValueError:
                        response.failure("JSON parsing error")
                else:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task
    def UC01_01_10_finish_topic(self):
        if self.user.environment.token:
            headers = self._get_headers()
            with self.client.put(f"/api/v1/user/topic/plan/{self.plan_id}/FINISHED", headers=headers,
                                 verify=False, catch_response=True,
                                 name="UC01_01_10 /api/v1/user/topic/plan/{self.plan_id}/FINISHED") as response:
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get("status") != "FINISHED":
                            response.failure(
                                "Request for finishing topic was sent, but couldn't find 'FINISHED' status in response")
                    except ValueError:
                        response.failure("JSON parsing error")
                else:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")


class RandomTaskSet(BehaviorBase):

    @task(10)
    def UC01_04_01_get_planning(self):
        if self.user.environment.token:
            headers = self._get_headers()
            with self.client.get(f"/planning", headers=headers, verify=False, catch_response=True,
                                 name="UC01_04_01 /planning") as response:
                if response.status_code != 200:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task(3)
    def UC01_04_02_get_profile_info(self):
        if self.user.environment.token:
            headers = self._get_headers()
            with self.client.get(f"/my-profile/info", headers=headers, verify=False, catch_response=True,
                                 name="UC01_04_02 /my-profile/info") as response:
                if response.status_code != 200:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task(5)
    def UC01_04_03_get_compilations(self):
        if self.user.environment.token:
            headers = self._get_headers()
            with self.client.get(f"/compilations", headers=headers, verify=False, catch_response=True,
                                 name="UC01_04_03 /compilations") as response:
                if response.status_code != 200:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task(1)
    def UC01_04_04_get_calendar(self):
        if self.user.environment.token:
            headers = self._get_headers()
            with self.client.get(f"/calendar", headers=headers, verify=False, catch_response=True,
                                 name="UC01_04_04 /calendar") as response:
                if response.status_code != 200:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task(3)
    def UC01_04_05_get_collegues(self):
        if self.user.environment.token:
            headers = self._get_headers()
            with self.client.get(f"/collegues", headers=headers, verify=False, catch_response=True,
                                 name="UC01_04_05 /collegues") as response:
                if response.status_code != 200:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task(3)
    def UC01_04_06_post_file(self):
        if self.user.environment.token:
            headers = self._get_headers()
            file_path = "Files/test_file.docx"
            with open(file_path, "rb") as file:
                file_name = os.path.basename(file_path)
                files = {"file": (file_name, file, "application/vnd.openxmlformats-officedocument.wordprocessingml"
                                                   ".document")}

                with self.client.post(f"/api/v1/service/file", files=files, headers=headers, verify=False,
                                      catch_response=True, name="UC01_04_06 /api/v1/service/file") as response:
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            if "uuid" not in data:
                                response.failure("Can't find id in response data")
                        except ValueError:
                            response.failure("JSON parsing error")
                    else:
                        response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")


class MixedBehavior(HttpUser):
    host = "https://polka-salt-test.x5.ru"
    wait_time = between(1, 5)

    # For test
    tasks = {ScormTaskSequence: 45, RandomTaskSet: 100}

    # For debug
    # tasks = [ScormTaskSequence]

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
        with self.client.post("/api/v1/login", data=json.dumps(request_data), headers=headers, verify=False,
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
