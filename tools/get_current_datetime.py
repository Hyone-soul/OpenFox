# tools/get_current_datetime.py
from open_fox.tools import tool
from datetime import datetime


@tool(name="get_current_datetime", description="获取当前的日期时间")
def get_current_datetime() -> str:
    """获取当前的日期时间

    Args:
        无
    """
    now = datetime.now()

    # 年-月-日 时:分:秒
    dt_str = now.strftime("%Y-%m-%d %H:%M:%S")
    return dt_str
