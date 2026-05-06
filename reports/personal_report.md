# Báo Cáo Cá Nhân - Lab 20 Multi-Agent Research System

## 1. Tổng Quan

Bài lab xây dựng một research assistant dùng LLM thật và so sánh hai hướng triển khai:

- **Single-agent baseline**: một agent gọi OpenAI `gpt-4o-mini` để trả lời toàn bộ truy vấn.
- **Multi-agent workflow**: Supervisor điều phối `Researcher -> Analyst -> Writer -> Critic -> done`.

Phiên bản mới nhất có Tavily live search cho Researcher và prompt Writer đã được siết để bắt buộc citation cho các claim quan trọng. Nếu không có `TAVILY_API_KEY` hoặc Tavily lỗi, hệ thống fallback về local corpus để vẫn chạy được.

## 2. Những Phần Đã Implement

- `LLMClient`: gọi OpenAI `gpt-4o-mini`, có timeout, retry, usage tracking và estimated cost.
- `SearchClient`: gọi Tavily Search API khi có `TAVILY_API_KEY`, fallback local corpus khi không có key.
- `SupervisorAgent`: route deterministic dựa trên shared state và max-iteration guard.
- `ResearcherAgent`: lấy sources, sau đó dùng LLM thật để viết research notes có citation.
- `AnalystAgent`: tạo thesis, key claims, tradeoffs, risks và confidence.
- `WriterAgent`: viết final answer dựa trên research notes, analysis notes và sources; prompt bắt buộc citation cho claim quan trọng.
- `CriticAgent`: fact-check final answer, kiểm tra citation coverage và unsupported claims.
- `Input guardrails`: chặn greeting/test message, query quá ngắn, request lấy secret/API key, prompt leakage và bypass request.
- `Run logging`: lưu mỗi lần chạy vào `runs/baseline/` hoặc `runs/multi-agent/`.
- `LangSmith tracing`: gửi hosted trace lên project `multi-agent-research-lab`.
- `benchmark` CLI: chạy 3 query mặc định và ghi `reports/benchmark_report.md`.

## 3. Thiết Kế Agent

| Agent | Vai trò | Input chính | Output chính |
|---|---|---|---|
| Supervisor | Quyết định node tiếp theo | `ResearchState` | route decision, `route_history` |
| Researcher | Thu thập evidence | query, audience, Tavily hoặc local fallback sources | `sources`, `research_notes` |
| Analyst | Phân tích evidence | query, sources, research notes | `analysis_notes` |
| Writer | Viết câu trả lời cuối có citation | research notes, analysis notes, sources | `final_answer` |
| Critic | Fact-check và kiểm tra citation | final answer, evidence, notes | `critic_notes` |

Các prompt LLM của Researcher, Analyst, Writer và Critic dùng cấu trúc:

- `<persona>`
- `<rules>`
- `<tools_instructions>`
- `<response_format>`
- `<constraints>`

Supervisor không dùng LLM prompt. Supervisor deterministic giúp route dễ giải thích, dễ test và không tốn thêm LLM call.

## 4. Shared State

Workflow dùng `ResearchState` làm object handoff duy nhất. Các field quan trọng:

- `request`: query, audience và `max_sources`.
- `iteration`: số bước routing đã chạy.
- `route_history`: thứ tự agent thực tế.
- `sources`: danh sách source lấy từ Tavily hoặc local fallback.
- `research_notes`: output của Researcher.
- `analysis_notes`: output của Analyst.
- `final_answer`: output của Writer.
- `critic_notes`: output fact-check của Critic.
- `agent_results`: nội dung từng agent kèm token/cost metadata.
- `trace`: event-level trace.
- `errors`: lỗi hoặc fallback reason.

Thiết kế này giúp debug được agent nào đã chạy, tạo ra nội dung gì, dùng nguồn nào, tốn bao nhiêu token/cost và vì sao workflow dừng.

## 5. Guardrails, Logs Và Observability

| Hạng mục | Cách triển khai |
|---|---|
| Input guardrails | Reject query không đáng research, quá ngắn, greeting/test message, secret request, prompt leakage, bypass request |
| Search fallback | Tavily live search nếu có key, local corpus nếu không có key hoặc API lỗi |
| Max iterations | `MAX_ITERATIONS=6` |
| Timeout | `TIMEOUT_SECONDS=60` |
| Retry | `LLMClient` retry OpenAI call tối đa 3 lần |
| Fallback | Workflow tạo fallback notes/answer nếu agent fail |
| Local trace | Ghi vào `state.trace` và `reports/multi_agent_trace.json` |
| Run logs | Lưu JSON trong `runs/baseline/` và `runs/multi-agent/` |
| LangSmith | Hosted trace trong project `multi-agent-research-lab` |
| Bonus Critic | Chạy sau Writer để fact-check final answer |

LangSmith span hiện có input/output đầy đủ cho từng node. Ví dụ Writer span có sources, research notes, analysis notes và final answer; Critic span có final answer, evidence và critic notes.

## 6. Kết Quả Kiểm Tra

Các lệnh kiểm tra đã pass:

```text
python -m pytest
10 passed

python -m ruff check src tests
All checks passed!

python -m mypy src
Success: no issues found in 28 source files
```

## 7. Kết Quả Benchmark Mới Nhất

| Run | Latency (s) | Cost (USD) | Tokens | Citation coverage | Failure rate | Quality | Ghi chú |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline-q1 | 14.99 | 0.0005 | 994 | N/A | 0% | 7.0 | completed |
| multi-agent-q1 | 30.28 | 0.0020 | 7588 | 80% | 0% | 8.5 | researcher > analyst > writer > critic > done |
| baseline-q2 | 12.40 | 0.0004 | 746 | N/A | 0% | 7.5 | completed |
| multi-agent-q2 | 25.36 | 0.0018 | 7378 | 60% | 0% | 8.5 | researcher > analyst > writer > critic > done |
| baseline-q3 | 14.24 | 0.0004 | 736 | N/A | 0% | 7.5 | completed |
| multi-agent-q3 | 25.36 | 0.0019 | 7845 | 100% | 0% | 9.0 | researcher > analyst > writer > critic > done |

Trung bình:

| Metric | Single-agent avg | Multi-agent avg | Nhận xét |
|---|---:|---:|---|
| Latency | 13.88s | 27.00s | Multi-agent chậm hơn khoảng 1.9 lần |
| Cost | 0.0004 USD | 0.0019 USD | Multi-agent tốn chi phí hơn vì có nhiều LLM calls và Tavily sources dài hơn |
| Tokens | 825 | 7604 | Multi-agent dùng nhiều token hơn |
| Citation coverage | N/A | 80.0% | Coverage tăng sau khi siết Writer prompt |
| Failure rate | 0% | 0% | Không có runtime failure |

## 8. Phân Tích Benchmark

Baseline nhanh hơn và rẻ hơn, nhưng thiếu observability. Không có research notes, không có source list có cấu trúc, không có route-level trace và không có Critic.

Multi-agent chậm hơn, nhưng thể hiện tốt yêu cầu của lab: role clarity, shared-state handoff, guardrails, traceability, benchmark và fact-check. Tavily giúp Researcher lấy nguồn live liên quan hơn. Prompt Writer mới giúp giảm lỗi thiếu citation: q3 tăng từ 0% ở lần trước lên 100%.

q2 vẫn chỉ đạt 60% citation coverage. Đây là dấu hiệu hệ thống còn có thể cải thiện bằng cách cho Critic route ngược lại Writer để revise answer khi coverage thấp.

## 9. Minh Chứng Trace

Trace được lưu ở local và hosted:

- `reports/multi_agent_trace.json`: trace đại diện mới nhất cho GraphRAG benchmark run dùng Tavily.
- `runs/baseline/*.json`: local baseline logs.
- `runs/multi-agent/*.json`: local multi-agent logs.
- LangSmith project: `multi-agent-research-lab`.

Ảnh minh chứng:

- `reports/langsmith_run_list.png`
- `reports/langsmith_run_tree.png`

Trace GraphRAG đại diện:

```text
researcher -> analyst -> writer -> critic -> done
```

Thông tin chính:

- Source provider: Tavily.
- Source count: 5.
- Citation coverage: 80%.
- Errors: 0.
- Researcher: 1602 tokens, 0.0004257 USD.
- Analyst: 997 tokens, 0.00031335 USD.
- Writer: 1952 tokens, 0.00057675 USD.
- Critic: 3037 tokens, 0.000636 USD.

## 10. Critic Findings

Critic xác nhận các claim được support khi có citation và nguồn phù hợp. Với q3, prompt Writer mới đã sửa được lỗi thiếu citation hoàn toàn trong lần benchmark này. Với q2, Critic vẫn cho thấy citation coverage còn thấp, nên hướng cải thiện tiếp theo là revise loop sau Critic.

Ý nghĩa của Critic:

- Phát hiện unsupported hoặc weak claims.
- Đo citation coverage.
- Chỉ ra lỗi Writer không cite đủ.
- Tạo evidence rõ ràng cho phần peer review và report.

## 11. Tự Đánh Giá Theo Rubric

| Criterion | Điểm kỳ vọng | Evidence |
|---|---:|---|
| Role clarity | 2/2 | Supervisor, Researcher, Analyst, Writer, Critic có trách nhiệm riêng |
| State design | 2/2 | Shared state có request, routes, sources, notes, final answer, critic notes, trace, errors, metadata |
| Failure guard | 2/2 | Có input guardrail, max iterations, timeout, retry, fallback, validation và Tavily fallback |
| Benchmark | 2/2 | Có baseline vs multi-agent với latency, cost, tokens, citation coverage, failure rate |
| Trace explanation | 2/2 | Có local JSON trace, run logs, LangSmith waterfall và input/output đầy đủ |

## 12. Exit Ticket

Nên dùng multi-agent khi task cần nhiều responsibility riêng như research, analysis, writing, fact-check hoặc khi cần audit trail rõ ràng. Không nên dùng multi-agent cho task đơn giản, rủi ro thấp hoặc khi một prompt đã đủ tốt, vì orchestration làm tăng latency, cost và độ phức tạp.

## 13. Kết Luận

Implementation hiện tại đáp ứng yêu cầu bài lab: dùng LLM thật, có baseline, có multi-agent workflow, có shared state, có guardrails, có Tavily live search với local fallback, có Writer citation prompt, có Critic bonus, có benchmark, có run logs và có LangSmith trace. Kết quả benchmark xác nhận tradeoff: multi-agent chậm và đắt hơn baseline, nhưng có khả năng inspect, debug và fact-check tốt hơn.
