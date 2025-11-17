# DAAR_Book-Engine

# 运行步骤
## 1. 下载项目
```bash
git clone https://github.com/yangl8/DAAR_Book_Engine.git
cd DAAR_Book_Engine
```

## 2. 创建,  激活虚拟环境
```bash
python3 -m venv venv
source venv/bin/activate     # mac / Linux
  # Windows: # venv\Scripts\activate
```

## 3. 进入 library 文件夹,安装依赖
```bash
cd library
pip install -r requirements.txt
```

## 4. 下载数据库文件(确保下载在library文件夹)
```bash
curl -L -o db_index.sqlite3 https://github.com/yangl8/DAAR_Book_Engine/releases/download/v1/db_index.sqlite3
```
## 5.  运行服务器
```bash
python manage.py runserver
```
最后
  打开http://127.0.0.1:8000/

