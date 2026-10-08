# create_engine：建立数据库连接的核心工具
# sessionmaker：用来创建"会话"（session）——每次读写数据库时，通过会话来操作
# declarative_base：提供一个基础模板，之后定义的表结构类要继承它
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 告诉SQLAlchemy：用SQLite数据库，数据库文件叫 health.db，存在当前项目文件夹下
DATABASE_URL = "sqlite:///./health.db"

# "引擎"：SQLAlchemy跟数据库真正打交道的核心组件，负责建立连接、执行SQL语句
# connect_args={"check_same_thread": False}：SQLite专属设置，允许FastAPI的多个线程共用同一个连接
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# "会话工厂"：之后每次要读写数据库，都通过它创建一个"会话"，相当于一次跟数据库对话的窗口
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# "总登记处"：任何类只要继承了Base（比如以后的User类），SQLAlchemy就会自动记住
# "这个类对应数据库里的哪张表、有哪些字段"，方便之后统一建表
Base = declarative_base()

# get_db：FastAPI会调用这个函数，来"要一个数据库连接"，交给路由函数使用
def get_db():
    # 调用SessionLocal（会话工厂），创建一个全新的数据库会话
    # 可以理解成"打开一扇跟数据库对话的窗口"，每次请求都开一扇全新的，互不干扰
    db = SessionLocal()
    try:
        # yield 和 return 不一样：return会结束整个函数；yield会暂停在这里，
        # 把db交给调用它的路由函数使用，函数本身没有结束，之后还能继续往下执行。
        # 路由函数执行完（不管成功还是报错），代码会跳回这里，继续执行yield之后的部分
        yield db
    finally:
        # try...finally：finally里的代码，不管前面发生了什么（成功还是报错），
        # 都保证会被执行到。这里保证不管请求处理结果如何，最后都会把这扇
        # "数据库对话窗口"关掉，避免忘记关闭连接导致资源一直被占用
        db.close()