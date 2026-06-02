"""部署配置分析 prompt 模板"""

DEPLOY_EXPLORE_PROMPT = """请分析以下部署配置文件，提取以下维度的结构化信息，以 JSON 格式输出：

严格规则：
1. 忽略 YAML/配置文件中的注释行(# 注释)，不将注释当作有效配置项
2. 只提取实际存在的配置值

分析维度：

1. **helm_chart**（如有 values.yaml）: 镜像版本、容器资源限制、PVC、Service/Ingress、ConfigMap
   格式: {"image": "...", "resources": {"cpu": "...", "memory": "..."}, "pvc": [...], "service": {...}, "ingress": {...}} 或 null

2. **dockerfile**（如有）: 基础镜像、构建步骤、暴露端口
   格式: {"base_image": "...", "expose_port": 8080, "build_steps": [...]} 或 null

3. **nginx_config**（如有）: 反向代理、路由规则、域名
   格式: {"upstreams": [...], "locations": [...], "server_names": [...]} 或 null

4. **cicd**（如有 Jenkinsfile/GitLab CI）: 构建流程、部署步骤
   格式: {"type": "Jenkinsfile", "stages": [...]} 或 null

5. **deployment_summary**: 综合部署方式判断
   格式: {"methods": ["K8s/Helm", "Docker"], "containers": [{"name": "...", "image": "..."}]}

以下是部署配置文件内容：

{source_code}"""