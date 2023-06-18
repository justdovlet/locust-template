import json
from queue import Queue

from locust import HttpUser, between, LoadTestShape
from locust import SequentialTaskSet, task
from locust import TaskSet

# Загружаем логины и пароли из файла
with open("files/credentials.txt", "r") as file:
    credentials = [tuple(line.strip().split(",")) for line in file.readlines()]

# Создаём очередь
credentials_queue = Queue()

# Кладём каждую пару логин-пароль внутрь
for cred in credentials:
    credentials_queue.put(cred)


# Пример последовательного набора задач
class YourSequentialTaskSetExample(SequentialTaskSet):
    wait_time = between(1, 5)  # время ожидания между задачами

    topic_id = None  # ID темы, который будет задан в UC01_01_01_your_get_example

    token = None
    headers = None

    password = None
    username = None

    # Метод, который вызывается при старте теста для каждого пользователя
    def on_start(self):
        if self.username is None:
            self.username, self.password = credentials_queue.get()  # получаем учетные данные из очереди

        # Определяем заголовки и данные для POST-запроса
        headers = {"Content-Type": "application/json"}
        request_data = {
            "username": self.username,
            "password": self.password
        }

        # Отправляем POST-запрос на авторизацию и обрабатываем ответ
        with self.client.post("/api/login", data=json.dumps(request_data), headers=headers, verify=False,
                              catch_response=True, name="UC01 Login") as response:
            # Если статус ответа равен 200, извлекаем токен доступа и сохраняем его
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("accessToken")  # сохраняем токен доступа
                self.headers = {"Authorization": f"Bearer {self.token}"}
            # Если статус ответа не равен 200, сообщаем о неожиданном статусе
            else:
                response.failure(
                    f"Unexpected status code: {response.status_code}. Request payload: {request_data}. Response: {response.text}")

    # Задача на получение темы
    @task
    def UC01_01_01_your_get_example(self):
        if self.token:
            self.topic_id = None
            headers = self.headers.copy()
            with self.client.get(
                    f"/api/get/topics", headers=headers, verify=False, catch_response=True,
                    name=f"{self.token}") as response:
                if response.status_code == 200:
                    try:
                        data = response.json()
                        self.topic_id = data["topicsStat"][0]["topicId"]  # получаем ID первой темы
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

    # Задача на отправку пост-запроса
    @task
    def UC01_01_02_your_post_example(self):
        if self.token:
            headers = self.headers.copy()
            headers["Content-Type"] = "application/json"
            request_data = {
                "topicId": self.topic_id,  # используем ID темы, полученный в UC01_01_01_your_get_example
            }
            with self.client.post(f"/api/user/topic/plan", data=json.dumps(request_data), headers=headers,
                                  verify=False, catch_response=True,
                                  name="UC01_01_02 /api/user/topic/plan") as response:
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

    # Метод, который вызывается при завершении теста для каждого пользователя
    def on_stop(self):
        if self.token:
            headers = {"Authorization": f'Bearer {self.token}'}
            with self.client.delete("/api/logout", headers=headers, verify=False,
                                    catch_response=True, name="UC01 Logout") as response:
                if response.status_code == 200:
                    self.token = None  # удаляем токен доступа
                    self.headers = None
                    if self.username and self.password:
                        credentials_queue.put((self.username, self.password))  # возвращаем учетные данные в очередь
                        self.username, self.password = None, None


# Пример случайного набора задач
class YourRandomTaskSetExample(TaskSet):
    wait_time = between(1, 5)  # время ожидания между задачами

    token = None
    headers = None

    password = None
    username = None

    def on_start(self):
        if self.username is None:
            self.username, self.password = credentials_queue.get()  # получаем учетные данные из очереди

        headers = {"Content-Type": "application/json"}
        request_data = {
            "username": self.username,
            "password": self.password
        }
        with self.client.post("/api/login", data=json.dumps(request_data), headers=headers, verify=False,
                              catch_response=True, name="UC01 Login") as response:
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("accessToken")  # сохраняем токен доступа
                self.headers = {"Authorization": f"Bearer {self.token}"}
            else:
                response.failure(
                    f"Unexpected status code: {response.status_code}. Request payload: {request_data}. Response: {response.text}")

    # Задачи с различными весами
    @task(10)
    def UC01_02_01_your_task(self):
        if self.token:
            headers = self.headers.copy()
            with self.client.get(f"/YourUrl", headers=headers, verify=False, catch_response=True,
                                 name="UC01_02_01 /YourUrl") as response:
                if response.status_code != 200:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    @task(20)
    def UC01_02_02_your_task(self):
        if self.token:
            headers = self.headers.copy()
            with self.client.get(f"/YourUrl", headers=headers, verify=False, catch_response=True,
                                 name="UC01_02_02 /YourUrl") as response:
                if response.status_code != 200:
                    response.failure(f"Unexpected status code: {response.status_code}. Response: {response.text}")

    def on_stop(self):
        if self.token:
            headers = {"Authorization": f'Bearer {self.token}'}
            with self.client.delete("/api/logout", headers=headers, verify=False,
                                    catch_response=True, name="UC01 Logout") as response:
                if response.status_code == 200:
                    self.token = None  # удаляем токен доступа
                    self.headers = None
                    if self.username and self.password:
                        credentials_queue.put((self.username, self.password))  # возвращаем учетные данные в очередь
                        self.username, self.password = None, None


# Класс, описывающий нагрузочный тест
class StepLoadShape(LoadTestShape):
    # Определение стадий нагрузки
    stages = [
        {"duration": 60, "users": 10, "spawn_rate": 10},
        {"duration": 120, "users": 50, "spawn_rate": 10},
        {"duration": 180, "users": 10, "spawn_rate": 10}
    ]

    def tick(self):
        # Получаем время выполнения нагрузочного теста
        run_time = self.get_run_time()

        # Цикл по стадиям нагрузки
        for stage in self.stages:
            if run_time < stage["duration"]:
                # Возвращаем число пользователей и скорость создания пользователей для текущей стадии
                tick_data = (stage["users"], stage["spawn_rate"])
                return tick_data

        # Если все стадии нагрузки завершены, возвращаем None
        return None


# Смешанное поведение пользователя
class MixedBehavior(HttpUser):
    host = "https://localhost"  # хост

    # Пропорции задач
    tasks = {YourSequentialTaskSetExample: 1, YourRandomTaskSetExample: 1}

# Locust запускается через терминал:
# locust -f max_perf_test.py
