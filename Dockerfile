FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema necesarias para mysqlclient (opcional, usamos pymysql)
RUN apt-get update && apt-get install -y gcc default-libmysqlclient-dev pkg-config && rm -rf /var/lib/apt/lists/*

# Copiar requirements.txt e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Exponer el puerto de Flask
EXPOSE 5000

# Comando para ejecutar la aplicación
CMD ["python", "run.py"]