# 安装指南

## 前置条件

- 已构建 Hermes 镜像：`bash scripts/build-image.sh`
- 本机可用 `python3` + PyYAML
- Git Bash / Linux bash（Windows 推荐 Git Bash）

## 校验专家包

```bash
bash expert-templates/bi-strategic-office/bin/validate.sh
bash expert-templates/bi-strategic-office/bin/doctor.sh --package-only
```

## 创建实例（新包流程）

```bash
bash scripts/create-instance.sh bi-strategic-office 8790 bi-strategic-office
```

`create-instance.sh` 检测到 `expert.yaml` + `bin/install.sh` 后，调用专家包安装器，不再走公共 BI 专属分支。

## 配置只读库

编辑 `instances/<profile>/.env`（勿提交真实密码）：

```env
FINANCE_BI_DSN=mssql+pymssql://readonly_user:PASSWORD@db-host:1433/bi_db
FINANCE_BI_DIALECT=mssql
FINANCE_BI_CHARSET=cp936
```

## 启动

```bash
bash scripts/up-instance.sh bi-strategic-office
```

启动后自动执行 `bin/post-start.sh`：安装插件 Python 依赖、校验 Toolset、运行 doctor。

## 手工安装 / 更新

```bash
bash expert-templates/bi-strategic-office/bin/install.sh \
  --profile bi-strategic-office \
  --instance-dir instances/bi-strategic-office \
  --data-dir instances/bi-strategic-office/data/hermes \
  --repo-root .

bash expert-templates/bi-strategic-office/bin/update.sh \
  --profile bi-strategic-office \
  --instance-dir instances/bi-strategic-office \
  --data-dir instances/bi-strategic-office/data/hermes \
  --repo-root .
```

## 诊断

```bash
bash expert-templates/bi-strategic-office/bin/doctor.sh \
  --profile bi-strategic-office \
  --data-dir instances/bi-strategic-office/data/hermes \
  --container hermes-bi-strategic-office
```
