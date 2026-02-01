# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY src/ ./src/

# Создаем директории для данных
RUN mkdir -p /app/data /app/config

# Запускаем бота
CMD ["python", "-m", "src.main"]
