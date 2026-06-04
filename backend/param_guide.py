"""FastAPI 参数获取与校验完整教程

本文件演示了前端向 FastAPI 后端传参的所有常见方式，
包括：查询参数、路径参数、请求体、表单、文件、请求头、Cookie 等。

运行方式：
    uv run python backend/param_guide.py

然后访问 http://localhost:8000/docs 查看自动生成的接口文档并测试。
"""

from enum import Enum
from typing import Annotated

from fastapi import (
    Body,
    Cookie,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="FastAPI 参数教程", version="1.0.0")

# 允许前端跨域访问，方便用浏览器测试
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 一、GET 查询参数 (Query Parameters) ====================


@app.get('/items/{bId}')
def readItemById(bId: int):
    print(f"id是{bId}, 类型是{type(bId)}")

    return {
        'message': 'ok',
        'success': True,
        'bId': bId
    }


@app.get("/users/{user_id}/items/{item_id}")
async def read_user_item(
    user_id: int, 
    item_id: str, 
    q: str | None = None, 
    short: bool = False,
    limit = 1
):
    item = {"item_id": item_id, "owner_id": user_id, "limit": limit}
    if q:
        item.update({"q": q})
    if not short:
        item.update(
            {"description": "This is an amazing item that has a long description"}
        )
    return item




# ==================== 三、POST JSON 请求体 (Request Body) ====================

# POST 的 JSON 请求体是最常见的传参方式，适合复杂数据结构


class Address(BaseModel):
    """嵌套模型：地址信息"""
    province: str = Field(..., min_length=2, max_length=20, description="省份")
    city: str = Field(..., min_length=2, max_length=20, description="城市")
    detail: str | None = Field(None, max_length=200, description="详细地址")


class CreateUserRequest(BaseModel):
    """创建用户的请求体模型 —— Pydantic 会自动校验和转换"""

    # Field(...) 中的 ... 表示必填字段
    name: str = Field(..., min_length=2, max_length=20, description="用户名")

    # str 类型，用 pattern 做简单邮箱格式校验
    email: str = Field(..., pattern=r"^[\w.-]+@[\w.-]+\.\w+$", description="邮箱地址")

    # ge=0, le=150 限制年龄范围
    age: int = Field(..., ge=0, le=150, description="年龄")

    # 布尔值，默认 False
    is_active: bool = Field(True, description="是否激活")

    # 列表字段，默认空列表；也可以指定元素类型约束
    hobbies: list[str] = Field(default_factory=list, description="兴趣爱好")

    # 嵌套模型，支持多层嵌套
    address: Address | None = Field(None, description="地址信息")

    # 使用 field_validator 进行自定义校验（字段级）
    @field_validator("name")
    @classmethod
    def name_must_not_be_numeric(cls, v: str) -> str:
        if v.isdigit():
            raise ValueError("用户名不能全是数字")
        return v.strip()


@app.post("/users")
def create_user(req: CreateUserRequest):
    """创建用户 —— 演示 POST JSON + Pydantic 模型校验

    请求体示例：
        {
            "name": "张三",
            "email": "zhangsan@example.com",
            "age": 25,
            "is_active": true,
            "hobbies": ["篮球", "编程"],
            "address": {
                "province": "浙江",
                "city": "杭州",
                "detail": "西湖区 xxx 路"
            }
        }
    """
    # 如果走到这里，说明 req 已经通过所有校验，可以直接使用
    return {
        "message": "用户创建成功",
        "data": req.model_dump(),
    }


class FilterParams(BaseModel):
    limit: int = Field(100, gt=0, le=100)
    offset: int = Field(0, ge=0)
    order_by: Literal["created_at", "updated_at"] = "created_at"
    tags: list[str] = []


@app.get("/items/")
async def read_items(filter_query: Annotated[FilterParams, Query()]):
    return filter_query

# 多个 Body 参数的情况（较少见，但前端可能传 {"user": {...}, "settings": {...}}）
class UserSettings(BaseModel):
    theme: str = "light"
    notifications: bool = True


@app.post("/users/with-settings")
def create_user_with_settings(
    user: Annotated[CreateUserRequest, Body(...)],
    settings: Annotated[UserSettings, Body(...)],
):
    """多个 Body 参数 —— 请求体需要按字段名嵌套

    请求体示例：
        {
            "user": {"name": "张三", "email": "zs@example.com", "age": 20},
            "settings": {"theme": "dark"}
        }
    """
    return {"user": user.model_dump(), "settings": settings.model_dump()}


# ==================== 四、POST 表单数据 (Form Data) ====================

# 表单提交（Content-Type: application/x-www-form-urlencoded）
# 常见于传统 HTML <form> 提交


@app.post("/login")
def login(
    # Form(...) 表示从表单数据中解析
    username: Annotated[str, Form(..., min_length=3, max_length=20, description="用户名")],
    password: Annotated[str, Form(..., min_length=6, description="密码")],
    # 表单也可以有可选字段
    remember: Annotated[bool, Form(description="记住我")] = False,
):
    """用户登录 —— 演示表单参数获取和校验

    前端可以用 fetch 这样传：
        const form = new FormData();
        form.append('username', 'admin');
        form.append('password', '123456');
        fetch('/login', { method: 'POST', body: new URLSearchParams(form) })
    """
    # 实际项目这里应该做密码比对，本示例只演示参数获取
    if username == "admin" and password == "123456":
        return {"message": "登录成功", "remember": remember}
    raise HTTPException(status_code=401, detail="用户名或密码错误")


# ==================== 五、文件上传 (File Upload) ====================

# 文件上传使用 UploadFile，支持大文件流式读取


@app.post("/upload")
async def upload_file(
    # File(...) 表示必填文件
    file: Annotated[UploadFile, File(..., description="要上传的文件")],
    # 可以同时接收普通表单字段
    folder: Annotated[str, Form(description="目标文件夹")] = "default",
):
    """单文件上传 —— 演示 UploadFile + 额外表单字段

    前端示例（HTML + JS）：
        const form = new FormData();
        form.append('file', fileInput.files[0]);
        form.append('folder', 'images');
        fetch('/upload', { method: 'POST', body: form });
    """
    # file.filename: 原始文件名
    # file.content_type: MIME 类型，如 image/png
    # file.size: 文件大小（字节）
    content = await file.read()
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(content),
        "folder": folder,
    }


# 多文件上传
@app.post("/upload/multiple")
async def upload_multiple(
    files: Annotated[list[UploadFile], File(..., description="多个文件")],
):
    """多文件上传

    前端示例：
        const form = new FormData();
        for (const f of fileInput.files) {
            form.append('files', f);
        }
        fetch('/upload/multiple', { method: 'POST', body: form });
    """
    results = []
    for file in files:
        content = await file.read()
        results.append({
            "filename": file.filename,
            "size": len(content),
        })
    return {"uploaded": results}


# 自定义文件校验：限制文件类型和大小
@app.post("/upload/image")
async def upload_image(
    file: Annotated[UploadFile, File(..., description="图片文件")],
):
    """带自定义校验的文件上传 —— 手动校验文件类型和大小"""
    # 校验文件类型
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"仅支持 JPEG/PNG/GIF/WebP 图片，当前类型: {file.content_type}",
        )

    content = await file.read()
    max_size = 5 * 1024 * 1024  # 5MB

    # 校验文件大小
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大支持 5MB，当前: {len(content) / 1024 / 1024:.2f}MB",
        )

    return {
        "filename": file.filename,
        "type": file.content_type,
        "size_kb": round(len(content) / 1024, 2),
    }


# ==================== 六、请求头 (Headers) ====================

# 获取前端发送的 HTTP 请求头，如 User-Agent、Authorization 等


@app.get("/headers")
def get_headers(
    # Header(None) 表示可选，默认 None
    user_agent: Annotated[str | None, Header(description="浏览器UA")] = None,
    # 自定义请求头，前端用 fetch 时传入：headers: { "X-Request-ID": "xxx" }
    request_id: Annotated[str | None, Header(alias="X-Request-ID", description="请求追踪ID")] = None,
    # 获取 Token（注意：真实项目应使用 OAuth2PasswordBearer 等标准方式）
    authorization: Annotated[str | None, Header(alias="Authorization", description="认证令牌")] = None,
):
    """获取请求头信息

    前端示例：
        fetch('/headers', {
            headers: {
                'X-Request-ID': 'uuid-123456',
                'Authorization': 'Bearer my-token'
            }
        })
    """
    return {
        "user_agent": user_agent,
        "request_id": request_id,
        "authorization": authorization,
    }


# ==================== 七、Cookie ====================

# 获取浏览器发送的 Cookie


@app.get("/cookies")
def get_cookies(
    # Cookie(None) 表示可选
    session_id: Annotated[str | None, Cookie(description="会话ID")] = None,
    preference: Annotated[str | None, Cookie(alias="user_pref", description="用户偏好")] = None,
):
    """获取 Cookie

    前端设置 Cookie：
        document.cookie = "session_id=abc123";
        document.cookie = "user_pref=dark_mode";
    """
    return {
        "session_id": session_id,
        "preference": preference,
    }


# ==================== 八、综合实战：分页查询 + 搜索 + 排序 ====================

class SortField(str, Enum):
    """排序字段枚举"""
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    NAME = "name"
    PRICE = "price"


class ProductListRequest(BaseModel):
    """商品列表查询请求体（POST 场景，适合复杂查询条件）"""
    keyword: str | None = Field(None, max_length=50, description="搜索关键词")
    category_ids: list[int] = Field(default_factory=list, description="分类ID列表")
    min_price: float | None = Field(None, ge=0, description="最低价格")
    max_price: float | None = Field(None, ge=0, description="最高价格")
    in_stock: bool | None = Field(None, description="是否有库存")
    sort_field: SortField = Field(SortField.CREATED_AT, description="排序字段")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="排序方向")

    # 跨字段校验：确保 min_price <= max_price
    @field_validator("max_price")
    @classmethod
    def check_price_range(cls, v: float | None, info) -> float | None:
        if v is not None:
            min_price = info.data.get("min_price")
            if min_price is not None and v < min_price:
                raise ValueError("最高价格不能低于最低价格")
        return v


class PaginationParams(BaseModel):
    """分页参数（常用组合，可复用）"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页条数")


@app.post("/products/list")
def list_products(
    filter_params: Annotated[ProductListRequest, Body(...)],
    page_params: Annotated[PaginationParams, Body(...)],
):
    """综合查询接口 —— POST + 多个 Body 参数 + 枚举 + 跨字段校验

    请求体示例：
        {
            "filter_params": {
                "keyword": "手机",
                "category_ids": [1, 2],
                "min_price": 1000,
                "max_price": 5000,
                "sort_field": "price",
                "sort_order": "asc"
            },
            "page_params": {
                "page": 1,
                "page_size": 20
            }
        }
    """
    # 模拟查询结果
    return {
        "filters": filter_params.model_dump(),
        "pagination": {
            **page_params.model_dump(),
            "offset": (page_params.page - 1) * page_params.page_size,
        },
        "total": 100,
        "data": [],
    }


# ==================== 九、混合传参（路径 + 查询 + Body + Header 同时存在） ====================

class UpdateStatusRequest(BaseModel):
    """更新状态请求体"""
    status: str = Field(..., pattern="^(active|inactive|deleted)$")
    reason: str | None = Field(None, max_length=500)


@app.put("/orders/{order_id}/status")
def update_order_status(
    *,
    # 路径参数
    order_id: Annotated[int, Path(..., gt=0)],
    # 查询参数
    notify_user: Annotated[bool, Query()] = True,
    # 请求体
    body: Annotated[UpdateStatusRequest, Body(...)],
    # 请求头
    operator: Annotated[str | None, Header(alias="X-Operator")] = None,
):
    """混合传参 —— 同时接收四种参数来源

    请求示例：
        PUT /orders/12345/status?notify_user=true
        Headers: X-Operator: admin
        Body: {"status": "active", "reason": "用户申请恢复"}
    """
    if not operator:
        raise HTTPException(status_code=400, detail="缺少操作人信息 (X-Operator)")

    return {
        "order_id": order_id,
        "new_status": body.status,
        "reason": body.reason,
        "notify_user": notify_user,
        "operator": operator,
    }


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("param_guide:app", host="0.0.0.0", port=8000, reload=True)
