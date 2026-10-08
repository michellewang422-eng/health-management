"""测试共用的数据库配置：一个内存 SQLite + 依赖覆盖，所有测试文件共享。

为什么要抽出来共享（而不是每个测试文件各写一遍）：
`app.dependency_overrides` 是一个**全局字典**。如果每个测试文件各建一个 engine、
各覆盖一次 get_db，后 import 的文件会盖掉先 import 的，一部分测试的请求就会
打到「没有建过表」的 engine 上，报 `no such table`。把 engine 和覆盖逻辑收敛到
这一个模块，所有测试文件共用同一个 engine，就没有这个问题。

三个关键机制：
1. 内存 SQLite（"sqlite://"）：不落盘、跑完即焚，不碰开发用的 health.db
2. StaticPool + check_same_thread=False：让 TestClient 的多个线程共用同一个
   内存连接，否则每个线程各开一个内存库，数据对不上
3. app.dependency_overrides[get_db]：把路由里的 Depends(get_db) 换成连测试库的
   版本，路由代码一行不用改
"""

import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
# 必须导入模型，Base 才知道有哪些表，下面 create_all 才建得出来
from app.models import HealthProfile  # noqa: F401


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """和 app/database.py 里的 get_db 结构一样，只是绑到测试用的 engine。"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


class DBTestCase(unittest.TestCase):
    """一个"已经把建表/删表/建 client 这些准备工作写好了的 TestCase"。
    所有用到数据库的测试类都继承它。

    setUp/tearDown 在每个 test_ 方法前后各自动跑一次，保证用例之间互不影响：
    每个用例开始前有一套干净的空表，结束后全部删掉。
    """

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)

    def tearDown(self):
        Base.metadata.drop_all(bind=engine)
