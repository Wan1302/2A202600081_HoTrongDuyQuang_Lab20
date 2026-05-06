# Báo Cáo Cá Nhân - Lab 20 Multi-Agent Research System

## 1. Tổng Quan

Bài lab xây dựng một research assistant dùng LLM thật và so sánh hai hướng triển khai:

- **Single-agent baseline**: một agent gọi OpenAI `gpt-4o-mini` để trả lời toàn bộ truy vấn.
- **Multi-agent workflow**: Supervisor điều phối qua `Researcher -> Analyst -> Writer -> Critic -> done`.

Mục tiêu chính là tạo hệ thống có thể kiểm tra được, không chỉ tạo câu trả lời cuối. Vì vậy implementation có shared state, route history, local JSON trace, LangSmith trace, run logs, token usage, estimated cost, guardrails và Critic fact-check.

## 2. Những Phần Đã Implement

- `LLMClient`: gọi OpenAI `gpt-4o-mini`, có timeout, retry, usage tracking và estimated cost.
- `SearchClient`: dùng local source corpus cố định để kết quả research có thể tái lập.
- `SupervisorAgent`: route deterministic dựa trên shared state và max-iteration guard.
- `ResearcherAgent`: chọn sources và viết research notes có citation.
- `AnalystAgent`: tạo thesis, key claims, tradeoffs, risks và confidence.
- `WriterAgent`: viết final answer dựa trên research notes, analysis notes và sources.
- `CriticAgent`: fact-check final answer, kiểm tra citation coverage và unsupported claims.
- `Input guardrails`: chặn greeting/test message, query quá ngắn, request lấy secret/API key, prompt leakage và bypass request.
- `Run logging`: lưu mỗi lần chạy vào `runs/baseline/` hoặc `runs/multi-agent/`.
- `LangSmith tracing`: gửi hosted trace lên project `multi-agent-research-lab`.
- `benchmark` CLI: chạy 3 query mặc định và ghi `reports/benchmark_report.md`.

## 3. Thiết Kế Agent

| Agent | Vai trò | Input chính | Output chính |
|---|---|---|---|
| Supervisor | Quyết định node tiếp theo | `ResearchState` | route decision, `route_history` |
| Researcher | Thu thập evidence | query, audience, local sources | `sources`, `research_notes` |
| Analyst | Phân tích evidence | query, sources, research notes | `analysis_notes` |
| Writer | Viết câu trả lời cuối | research notes, analysis notes, sources | `final_answer` |
| Critic | Fact-check và kiểm tra citation | final answer, evidence, notes | `critic_notes` |

Các prompt LLM của Researcher, Analyst, Writer và Critic dùng cấu trúc rõ ràng gồm:

- `<persona>`
- `<rules>`
- `<tools_instructions>`
- `<response_format>`
- `<constraints>`

Supervisor không dùng LLM prompt. Supervisor được làm deterministic để route dễ giải thích, dễ test và không tốn thêm LLM call.

## 4. Shared State

Workflow dùng `ResearchState` làm object handoff duy nhất. Các field quan trọng:

- `request`: query, audience và `max_sources`.
- `iteration`: số bước routing đã chạy.
- `route_history`: thứ tự agent thực tế.
- `sources`: danh sách source có thể cite.
- `research_notes`: output của Researcher.
- `analysis_notes`: output của Analyst.
- `final_answer`: output của Writer.
- `critic_notes`: output fact-check của Critic.
- `agent_results`: nội dung từng agent kèm token/cost metadata.
- `trace`: event-level trace.
- `errors`: lỗi hoặc fallback reason.

Thiết kế này giúp debug được agent nào đã chạy, tạo ra nội dung gì, tốn bao nhiêu token/cost và vì sao workflow dừng.

## 5. Guardrails, Logs Và Observability

| Hạng mục | Cách triển khai |
|---|---|
| Input guardrails | Reject query không đáng research, quá ngắn, greeting/test message, secret request, prompt leakage, bypass request |
| Max iterations | `MAX_ITERATIONS=6` |
| Timeout | `TIMEOUT_SECONDS=60` |
| Retry | `LLMClient` retry OpenAI call tối đa 3 lần |
| Fallback | Workflow tạo fallback notes/answer nếu agent fail |
| Local trace | Ghi vào `state.trace` và `reports/multi_agent_trace.json` |
| Run logs | Lưu JSON trong `runs/baseline/` và `runs/multi-agent/` |
| LangSmith | Hosted trace trong project `multi-agent-research-lab` |
| Bonus Critic | Chạy sau Writer để fact-check final answer |

Sau lần sửa mới nhất, LangSmith không chỉ hiển thị state summary mà còn có input/output đầy đủ cho từng node. Ví dụ Writer span có input gồm `research_notes`, `analysis_notes`, `sources` và output gồm `final_answer`; Critic span có input gồm final answer và evidence, output gồm `critic_notes`.

## 6. Kết Quả Kiểm Tra

Các lệnh kiểm tra đã pass:

```text
python -m pytest
8 passed

python -m ruff check src tests
All checks passed!

python -m mypy src
Success: no issues found in 28 source files
```

## 7. Kết Quả Benchmark Mới Nhất

| Run | Latency (s) | Cost (USD) | Tokens | Citation coverage | Failure rate | Quality | Ghi chú |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline-q1 | 14.02 | 0.0005 | 932 | N/A | 0% | 7.0 | completed |
| multi-agent-q1 | 29.68 | 0.0013 | 4699 | 20% | 0% | 8.5 | researcher > analyst > writer > critic > done |
| baseline-q2 | 11.51 | 0.0004 | 762 | N/A | 0% | 7.5 | completed |
| multi-agent-q2 | 28.75 | 0.0014 | 5021 | 100% | 0% | 9.0 | researcher > analyst > writer > critic > done |
| baseline-q3 | 12.92 | 0.0004 | 707 | N/A | 0% | 7.5 | completed |
| multi-agent-q3 | 33.01 | 0.0014 | 5140 | 100% | 0% | 9.0 | researcher > analyst > writer > critic > done |

Trung bình:

| Metric | Single-agent avg | Multi-agent avg | Nhận xét |
|---|---:|---:|---|
| Latency | 12.82s | 30.48s | Multi-agent chậm hơn khoảng 2.4 lần |
| Cost | 0.0004 USD | 0.0014 USD | Multi-agent tốn chi phí hơn |
| Tokens | 800 | 4953 | Multi-agent dùng nhiều token hơn vì có nhiều node |
| Citation coverage | N/A | 73.3% | Multi-agent đo được citation coverage |
| Failure rate | 0% | 0% | Không có runtime failure |

## 8. Phân Tích Benchmark

Baseline là lựa chọn nhanh và rẻ hơn. Tuy nhiên, output của baseline khó audit vì không có intermediate reasoning, không có source list có cấu trúc, không có Critic và không đo citation coverage.

Multi-agent đắt hơn và chậm hơn, nhưng phù hợp hơn với yêu cầu bài lab. Hệ thống thể hiện rõ role clarity, state handoff, routing trace, observability và fact-check. Đặc biệt, Critic giúp phát hiện khi final answer có citation coverage thấp hoặc claim vượt quá evidence.

Kết quả query GraphRAG cho thấy citation coverage chỉ 20%. Đây không phải runtime bug, mà là quality signal: Writer chủ yếu dựa vào nguồn Microsoft Research trực tiếp, trong khi các nguồn còn lại nói về agent workflow, orchestration và tracing. Critic đã chỉ ra các claim cần viết thận trọng hơn khi chưa có comparative metrics.

## 9. Minh Chứng Trace

Trace được lưu ở local và hosted:

- Local representative trace: `reports/multi_agent_trace.json`.
- Local run logs: `runs/baseline/*.json` và `runs/multi-agent/*.json`.
- Hosted trace: LangSmith project `multi-agent-research-lab`.

Ảnh minh chứng trong `reports`:

- `langsmith_run_list.png`: danh sách run trên LangSmith.
- `langsmith_run_tree.png`: waterfall trace của `multi_agent_workflow`.

Trace GraphRAG đại diện có route:

```text
researcher -> analyst -> writer -> critic -> done
```

Các event chính:

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

## 10. Critic Findings

Critic xác nhận các claim có hỗ trợ:

- GraphRAG dùng graph-based indexes cho query-focused summarization.
- GraphRAG xử lý local/global context theo nguồn Microsoft Research.
- Citation `[1]` khớp với source list.

Critic cũng cảnh báo:

- Citation coverage của query GraphRAG thấp.
- Một số claim như “significantly enhances”, “particularly effective” hoặc “powerful tool” cần qualify vì chưa có performance metrics.
- Nên nêu rõ các khoảng trống evidence thay vì viết như kết luận chắc chắn.

Điểm này giúp hệ thống có khả năng tự kiểm tra chất lượng thay vì chỉ sinh câu trả lời cuối.

## 11. Tự Đánh Giá Theo Rubric

| Criterion | Điểm kỳ vọng | Evidence |
|---|---:|---|
| Role clarity | 2/2 | Supervisor, Researcher, Analyst, Writer, Critic có trách nhiệm riêng |
| State design | 2/2 | Shared state có request, routes, sources, notes, final answer, critic notes, trace, errors, metadata |
| Failure guard | 2/2 | Có input guardrail, max iterations, timeout, retry, fallback, validation |
| Benchmark | 2/2 | Có baseline vs multi-agent với latency, cost, tokens, citation coverage, failure rate |
| Trace explanation | 2/2 | Có local JSON trace, run logs và LangSmith waterfall |

## 12. Exit Ticket

Nên dùng multi-agent khi task cần nhiều responsibility riêng như research, analysis, writing, fact-check hoặc khi cần audit trail rõ ràng. Không nên dùng multi-agent cho task đơn giản, rủi ro thấp hoặc khi một prompt đã đủ tốt, vì orchestration làm tăng latency, cost và độ phức tạp.

## 13. Kết Luận

Implementation hiện tại đáp ứng yêu cầu bài lab: dùng LLM thật, có baseline, có multi-agent workflow, có shared state, có guardrails, có Critic bonus, có benchmark, có run logs và có LangSmith trace. Tradeoff đo được là multi-agent chậm hơn và tốn chi phí hơn, nhưng dễ inspect, debug và fact-check hơn nhiều so với baseline.
