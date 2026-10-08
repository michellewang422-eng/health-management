"""专门负责"问 User-management-service：这个用户存在吗"。

这是 server 调用 server：health-service 在这里扮演 client，
User-management-service 扮演 server。
"""

import httpx

# User-management-service 的地址；它跑在 8000 端口，我们自己是 8001
USER_SERVICE_URL = "http://127.0.0.1:8000"


# 自定义异常：表示"问不到答案"（对方挂了、超时、返回了奇怪的状态码）。
# 它和"用户不存在"是两回事：前者是 502（上游出问题），后者是 404（用户确实没有）
class UserServiceUnavailable(Exception):
    pass


def user_exists(user_id: int) -> bool:
    try:
        # timeout=3.0：最多等 3 秒。不设超时的话，对方卡住会让我们也一直卡住
        r = httpx.get(f"{USER_SERVICE_URL}/users/{user_id}", timeout=3.0)
    except httpx.HTTPError:          # 连不上、超时等网络层错误
        raise UserServiceUnavailable()
    if r.status_code == 200:
        return True
    if r.status_code == 404:
        return False
    raise UserServiceUnavailable()   # 500 等其它情况：不敢断定用户存不存在


def get_user_checker():
    """依赖函数：路由通过 Depends(get_user_checker) 拿到 user_exists。

    为什么多包一层而不是路由里直接调 user_exists？
    因为测试时可以用 app.dependency_overrides 把它整个换成"假的"，
    测试就不需要真的启动 User-management-service，也不依赖网络。
    """
    return user_exists
