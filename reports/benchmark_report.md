# Báo cáo benchmark

## Tóm tắt

Báo cáo này so sánh hai cách triển khai cho cùng một bài toán research assistant:

- **Single-agent baseline**: một lần gọi `gpt-4o-mini` xử lý toàn bộ truy vấn.
- **Multi-agent workflow**: Supervisor điều phối qua Researcher, Analyst, Writer và Critic.

Tất cả các lần chạy benchmark đều hoàn thành thành công với **failure rate 0%**. Workflow multi-agent chậm hơn và dùng nhiều token hơn, nhưng đổi lại có handoff rõ ràng, trace chi tiết, citation coverage đo được và bước Critic để fact-check final answer.

## Môi trường chạy
- Model: `gpt-4o-mini`
- Runtime: local Python virtual environment
- Trace: local JSON trace và LangSmith hosted trace
- Các lệnh kiểm tra:
  - `python -m pytest`: 5 passed
  - `python -m ruff check src tests`: all checks passed
  - `python -m mypy src`: success, no issues in 27 source files

## Bảng kết quả

| Run | Latency (s) | Cost (USD) | Tokens | Citation coverage | Failure rate | Quality | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline-q1 | 13.60 | 0.0005 | 972 | N/A | 0% | 7.0 | completed |
| multi-agent-q1 | 32.28 | 0.0014 | 4949 | 20% | 0% | 8.5 | route=researcher > analyst > writer > critic > done |
| baseline-q2 | 9.49 | 0.0004 | 800 | N/A | 0% | 7.5 | completed |
| multi-agent-q2 | 32.60 | 0.0014 | 4925 | 100% | 0% | 9.0 | route=researcher > analyst > writer > critic > done |
| baseline-q3 | 8.38 | 0.0003 | 671 | N/A | 0% | 7.5 | completed |
| multi-agent-q3 | 30.13 | 0.0015 | 5305 | 100% | 0% | 9.0 | route=researcher > analyst > writer > critic > done |

Quality là điểm tự đánh giá trước peer review theo thang 0-10. Điểm này xét đến độ đúng trọng tâm, cấu trúc câu trả lời, citation coverage, traceability, failure handling và bước fact-check của Critic.

## So sánh trung bình

| Metric | Single-agent avg | Multi-agent avg | Nhận xét |
|---|---:|---:|---|
| Latency | 10.49s | 31.67s | Multi-agent chậm hơn khoảng 3.0 lần vì có nhiều LLM calls và thêm Critic. |
| Cost | 0.0004 USD | 0.0014 USD | Multi-agent tốn chi phí khoảng 3.6 lần trong lần chạy này. |
| Tokens | 814 | 5060 | Multi-agent dùng khoảng 6.2 lần token do có research, analysis, writing và critic notes. |
| Citation coverage | N/A | 73.3% | Baseline không dùng structured sources; multi-agent đo được coverage nguồn. |
| Failure rate | 0% | 0% | Cả hai cách đều chạy thành công. |

## Phân tích kết quả

Baseline nhanh hơn và rẻ hơn vì chỉ dùng một lần gọi LLM. Cách này phù hợp khi truy vấn đơn giản, rủi ro thấp hoặc không cần auditability cao. Tuy nhiên, baseline khó kiểm tra hơn vì không tách riêng research notes, analysis notes, final answer và fact-check.

Workflow multi-agent tăng latency, cost và token usage, đặc biệt sau khi thêm Critic. Đây là tradeoff có chủ đích: hệ thống có thêm một bước kiểm tra final answer trước khi kết thúc. Critic giúp phát hiện unsupported claims, overstated claims và vấn đề citation, điều mà baseline không expose rõ.

Citation coverage của multi-agent đạt trung bình 73.3%. Query 1 vẫn chỉ đạt 20% vì Writer chủ yếu cite nguồn Microsoft GraphRAG chính. Tuy nhiên, Critic đã phát hiện vấn đề này và ghi rõ citation coverage thấp, đồng thời chỉ ra các claim cần qualify hoặc cần thêm evidence. Query 2 và query 3 đạt 100% citation coverage, cho thấy workflow có khả năng sử dụng source tốt hơn ở các task phù hợp.

## Giải thích trace

Trace đại diện cho query GraphRAG đi theo route:

```text
workflow.started
supervisor.route -> researcher
researcher.completed
supervisor.route -> analyst
analyst.completed
supervisor.route -> writer
writer.completed
supervisor.route -> critic
critic.completed
supervisor.route -> done
workflow.completed
```

Các giá trị cụ thể từ `reports/multi_agent_trace.json`:

- Route history: `researcher > analyst > writer > critic > done`
- Số iteration: 5
- Số nguồn thu thập: 5
- Researcher usage: 624 tokens, 0.00016605 USD
- Analyst usage: 719 tokens, 0.0002595 USD
- Writer usage: 1578 tokens, 0.0005598 USD
- Critic usage: 2043 tokens, 0.00045315 USD
- Citation coverage query GraphRAG: 20%
- Errors: không có

Critic fact-check đã ghi nhận:

- Final answer có các claim được support bởi source Microsoft Research.
- Citation `[1]` khớp source list.
- Citation coverage thấp vì final answer chủ yếu dùng source `[1]`.
- Một số claim như “potentially outperforms traditional summarization methods” bị đánh dấu là overstated vì không có performance metrics hoặc comparative analysis.
- Critic đề xuất qualify hoặc loại bỏ các claim vượt quá evidence.

## Minh chứng LangSmith

Trace được ghi ở hai nơi:

- Local JSON trace trong `reports/multi_agent_trace.json`.
- LangSmith hosted trace trong project `multi-agent-research-lab`.

Minh chứng LangSmith nằm trong folder `reports`:

- [langsmith_run_list.png](langsmith_run_list.png): danh sách runs có root run `multi_agent_workflow`.
- [langsmith_run_tree.png](langsmith_run_tree.png): waterfall trace gồm Supervisor, Researcher, Analyst, Writer và Critic.

Trên LangSmith, root run là `multi_agent_workflow`. Waterfall mới gồm:

```text
supervisor
researcher
supervisor
analyst
supervisor
writer
supervisor
critic
supervisor
```

LangSmith cũng hiển thị input query, graph nodes, `max_iterations=6`, `timeout_seconds=60`, latency tổng và latency từng worker. Trace này chứng minh workflow multi-agent có orchestration thật, không chỉ là một prompt đơn lẻ.

## Failure mode

Không có runtime failure trong benchmark. Failure mode chính quan sát được là **citation coverage thấp ở query 1** và một số claim trong final answer bị Critic đánh giá là vượt quá evidence.

Nguyên nhân:

- Source corpus có một nguồn GraphRAG trực tiếp, các nguồn còn lại thiên về agent workflow/tracing.
- Writer tập trung vào source `[1]`, nguồn liên quan nhất cho GraphRAG.
- Một số phrasing trong final answer như “potentially outperforms” cần comparative evidence nhưng source hiện tại chưa cung cấp.

Cách khắc phục:

- Siết prompt của Writer để tránh claim so sánh nếu không có performance metrics.
- Bổ sung search/live web hoặc thêm source GraphRAG chuyên sâu hơn.
- Giữ Critic là bước bắt buộc sau Writer để phát hiện unsupported claims trước khi nộp final answer.

## Kết luận

Multi-agent không phải cách nhanh nhất hoặc rẻ nhất, nhưng là phương án phù hợp hơn cho bài lab này. Nó thể hiện rõ role clarity, shared state handoff, guardrail, traceability, benchmark-driven evaluation và bonus Critic fact-check. Kết quả benchmark xác nhận tradeoff dự kiến: multi-agent tốn thêm latency/cost/token, nhưng dễ inspect, debug và đánh giá hơn cho các task research phức tạp.
