# Crawlee Worker

Worker phụ trợ cho ứng dụng Social Listening. Netlify app dùng Gemini/Google/RSS để tìm URL, sau đó gọi worker này để bóc dữ liệu bài viết thật: tiêu đề, sapo, nguồn, canonical URL và ngày đăng.

Worker không quét dữ liệu từ nền tảng mạng xã hội Meta và không crawl tài khoản/fanpage.

## Chạy local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Endpoint:

```txt
POST http://localhost:8000/crawl
```

## Deploy

Có thể deploy bằng Docker trên Render, Railway, Fly.io, VPS hoặc Apify.

Sau khi deploy, cấu hình Netlify:

```txt
CRAWLEE_WORKER_URL=https://your-worker-domain/crawl
CRAWLEE_WORKER_TOKEN=mot-token-dai-kho-doan
CRAWLEE_MAX_URLS=40
CRAWLEE_TIMEOUT_MS=20000
```

Nếu đặt `CRAWLEE_WORKER_TOKEN` trên worker, cần đặt cùng giá trị trên Netlify app. Netlify sẽ gửi token qua header `x-worker-token`.

Nếu worker chậm, giảm `CRAWLEE_MAX_URLS` xuống `15` hoặc `20`.
