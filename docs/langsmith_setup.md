# Hướng dẫn tích hợp LangSmith

## 1. Tạo LangSmith API key

1. Đăng nhập LangSmith.
2. Tạo hoặc chọn workspace/project cho bài lab.
3. Tạo API key.
4. Không commit API key vào Git.

## 2. Cấu hình `.env`

Mở file `.env` và thêm hoặc sửa các biến sau:

```text
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_PROJECT=multi-agent-research-lab
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

Các biến OpenAI vẫn cần giữ nguyên:

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

## 3. Chạy lại multi-agent để tạo hosted trace

```powershell
python -m multi_agent_research_lab.cli multi-agent --query "Research GraphRAG state-of-the-art and write a 500-word summary" | Tee-Object -FilePath reports\multi_agent_trace.json
```

Sau khi chạy xong, mở LangSmith project `multi-agent-research-lab`. Bạn sẽ thấy root run `multi_agent_workflow` và các child runs:

- `supervisor`
- `researcher`
- `supervisor`
- `analyst`
- `supervisor`
- `writer`
- `supervisor`
- `critic`
- `supervisor`
- `supervisor`

Local JSON trace vẫn được lưu trong `reports/multi_agent_trace.json`.

## 4. Chạy baseline trace

```powershell
python -m multi_agent_research_lab.cli baseline --query "Research GraphRAG state-of-the-art and write a 500-word summary"
```

LangSmith sẽ ghi run `single_agent_baseline`.

## 5. Chạy benchmark

```powershell
python -m multi_agent_research_lab.cli benchmark
```

Benchmark sẽ tạo nhiều run trên LangSmith, tương ứng với baseline và multi-agent của từng query.

## 6. Kiểm tra trước khi nộp

```powershell
python -m pytest
python -m ruff check src tests
python -m mypy src
```

## 7. Nội dung nên ghi vào báo cáo

Nếu LangSmith chạy thành công, có thể ghi:

```text
Ngoài local JSON trace trong ResearchState.trace, hệ thống còn tích hợp LangSmith.
Khi LANGSMITH_TRACING=true và LANGSMITH_API_KEY được cấu hình, workflow gửi root run
multi_agent_workflow và các child run supervisor/researcher/analyst/writer lên project
multi-agent-research-lab.
```

Nếu cần nộp screenshot, chụp màn hình LangSmith run tree của query GraphRAG.
