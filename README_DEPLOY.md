# 今天吃啥 v4 数据库版部署说明

## 1. 建 Supabase 表

打开 Supabase Dashboard -> SQL Editor，新建 Query，把 `supabase_schema.sql` 全部复制进去运行。

## 2. 导入 Excel 初始数据

在 PowerShell 里进入本目录：

```powershell
cd D:\桌面\my-project\website_construct
$env:SUPABASE_SERVICE_ROLE_KEY="你的 service_role key"
python scripts\import_initial_data.py --dry-run
python scripts\import_initial_data.py --reset
```

`service_role key` 只用于本机导入数据，不能放到 HTML、GitHub 或 Vercel 环境变量里。

## 3. 可选：开启审核入口

页面默认会隐藏“审核”。如果你要审核别人新增店铺：

1. 打开 `index.html`，让页面匿名登录一次。
2. 去 Supabase Dashboard -> Authentication -> Users 找到你的 user id。
3. 在 `index.html` 里把 `ADMIN_USER_ID` 改成这个 id。
4. 在 SQL Editor 运行：

```sql
insert into public.app_admins(user_id) values ('你的 user id')
on conflict (user_id) do nothing;
```

## 4. 部署到 Vercel

```powershell
npm i -g vercel
cd D:\桌面\my-project\website_construct
vercel
vercel --prod
```

部署后，别人新增评论会写入 Supabase，并通过 Realtime 自动刷新弹幕、推荐卡、搜索页和排行榜。
