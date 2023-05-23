import json
import math
from queue import Queue
from locust import HttpUser, between, LoadTestShape
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


# Базовый класс задач для поведения, предоставляет методы для получения заголовков и хоста
class BehaviorBase(TaskSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # Метод для получения заголовков запроса
    def _get_headers(self):
        return {"Authorization": f'Bearer {self.user.environment.token}'}

    # Метод для получения хоста
    def _get_host(self):
        return self.user.environment.host


# Пример последовательного набора задач
class YourSequentialTaskSetExample(SequentialTaskSet, BehaviorBase):
    topic_id = None  # ID темы, который будет задан в UC01_01_01_your_get_example

    # Задача на получение темы
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
        if self.user.environment.token:
            headers = self._get_headers()
            headers["Content-Type"] = "application/json"
            request_data = {
                "topicId": self.topic_id,  # используем ID темы, полученный в UC01_01_01_your_get_example
            }
            with self.client.post(f"/api/v1/user/topic/plan", data=json.dumps(request_data), headers=headers,
                                  verify=False, catch_response=True,
                                  name="UC01_01_02 /api/v1/user/topic/plan") as response:
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


# Пример случайного набора задач
class YourRandomTaskSetExample(BehaviorBase):

    # Задачи с различными весами
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


class StepLoadShape(LoadTestShape):
    """
    Форма ступенчатой нагрузки

    Аргументы:

        step_time -- Время между ступенями
        step_load -- Количество пользователей, увеличивающееся на каждой ступени
        spawn_rate -- Сколько пользователей запускать/останавливать в секунду на каждой ступени
        time_limit -- Длительность всего теста


    """

    step_time = 30
    step_load = 10
    spawn_rate = 10
    time_limit = 600

    def tick(self):
        run_time = self.get_run_time()

        if run_time > self.time_limit:
            return None

        current_step = math.floor(run_time / self.step_time) + 1
        return current_step * self.step_load, self.spawn_rate


# Смешанное поведение пользователя
class MixedBehavior(HttpUser):
    host = "https://yourhost.com"  # хост
    wait_time = between(1, 5)  # время ожидания между задачами

    # Пропорции задач
    tasks = {YourSequentialTaskSetExample: 1, YourRandomTaskSetExample: 1}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.username, self.password = None, None  # учетные данные пользователя

    # Метод, выполняющийся при старте теста
    def on_start(self):
        if self.username is None:
            self.username, self.password = credentials_queue.get()  # получаем учетные данные из очереди
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
                self.environment.token = data.get("accessToken")  # сохраняем токен доступа

    # Метод, выполняющийся при завершении теста
    def on_stop(self):
        if self.environment.token:
            headers = {"Authorization": f'Bearer {self.environment.token}'}
            with self.client.delete("/api/logout", headers=headers, verify=False,
                                    catch_response=True, name="UC01 Logout") as response:
                if response.status_code == 200:
                    self.environment.token = None  # удаляем токен доступа
                    if self.username is not None:
                        credentials_queue.put((self.username, self.password))  # возвращаем учетные данные в очередь
                        self.username, self.password = None, None


# Locust запускается через терминал:
# locust -f main.py
