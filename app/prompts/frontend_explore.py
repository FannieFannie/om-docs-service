"""前端代码分析 prompt 模板"""

FRONTEND_EXPLORE_PROMPT = """请分析以下前端源码，提取以下维度的结构化信息，以 JSON 格式输出：

严格规则：
1. 忽略所有代码注释，绝不将注释内容写入分析结果
2. 从组件名、路由路径、菜单项推断功能含义
3. 只提取实际存在的结构，不存在的内容不输出

分析维度：

1. **routes**: 所有页面路由路径和对应组件
   格式: [{"path": "/xxx", "component": "XxxPage", "name": "功能名称"}]

2. **menus**: 导航菜单层级结构
   格式: [{"name": "一级菜单", "icon": "xxx", "children": [{"name": "二级菜单", "path": "/xxx"}]}]

3. **page_components**: 每个页面的功能、表格列定义、表单字段
   格式: [{"page": "XxxPage", "tables": [{"columns": ["列1", "列2"]}], "forms": [{"fields": ["字段1", "字段2"]}]}]

4. **layout**: 布局框架类型（大屏展示/后台管理/混合型）
   格式: {"type": "后台管理", "container_class": "ant-layout"}

5. **auth_guard**: 登录页结构、token 存储方式（localStorage/cookie/session）
   格式: {"login_path": "/login", "token_storage": "localStorage", "token_key": "token"}

6. **ui_library**: UI 库识别（Ant Design/Element UI/Material UI/其他）
   格式: {"name": "Ant Design", "version": "4.x"}

7. **routing_mode**: 路由模式（hash/history）
   格式: "hash"

以下是前端源码文件内容：

{source_code}"""