# Báo cáo cá nhân - Lab 20 Multi-Agent Research System

## Hồ Trọng Duy Quang - 2A202600081

## 1. Tổng quan

Bài lab này xây dựng một research assistant và so sánh hai cách triển khai:

- **Single-agent baseline**: một lần gọi OpenAI `gpt-4o-mini` trả lời toàn bộ truy vấn.
- **Multi-agent workflow**: Supervisor điều phối task qua Researcher, Analyst, Writer và Critic.

Mục tiêu không chỉ là tạo ra câu trả lời cuối cùng, mà còn làm cho quá trình tạo câu trả lời có thể kiểm tra được. Hệ thống lưu route history, shared state, local JSON trace, LangSmith hosted trace, token usage, estimated cost, errors và critic notes.

## 2. Tóm tắt phần đã triển khai

Các thành phần đã hoàn thành:

- `LLMClient`: gọi OpenAI `gpt-4o-mini` bằng `OPENAI_API_KEY`, có timeout, retry, usage tracking và estimated cost.
- `SearchClient`: dùng local source corpus cố định để Researcher tạo research notes có citation một cách reproducible.
- `SupervisorAgent`: router rule-based với max-iteration guard.
- `ResearcherAgent`: thu thập sources và viết research notes có citation.
- `AnalystAgent`: rút ra thesis, claims, tradeoffs, risks và confidence.
- `WriterAgent`: viết final response chỉ dựa trên research notes, analysis notes và sources trong shared state.
- `CriticAgent`: bonus fact-check agent kiểm tra final answer, citation usage và unsupported claims dựa trên evidence trong shared state.
- `MultiAgentWorkflow`: điều phối state machine, lưu local trace, LangSmith trace và fallback behavior.
- `benchmark` CLI: so sánh baseline và multi-agent, sau đó ghi `reports/benchmark_report.md`.

## 3. Thiết kế prompt

Các prompt gọi LLM đều dùng cấu trúc rõ ràng:

- `<persona>`: định nghĩa vai trò của agent.
- `<rules>`: quy định hành vi chính của agent.
- `<tools_instructions>`: nói rõ agent được dùng input nào và giới hạn tool ra sao.
- `<response_format>`: định dạng output mong muốn.
- `<constraints>`: ngăn hallucinated citation, unsupported claims và role overlap.

Supervisor không dùng LLM prompt. Supervisor dùng deterministic routing để trace dễ giải thích và workflow không bị route khó đoán.

## 4. Vai trò của từng agent

| Agent | Responsibility | Input | Output |
|---|---|---|---|
| Supervisor | Chọn route tiếp theo hoặc dừng workflow | Shared `ResearchState` | `route_history`, trace, route decision |
| Researcher | Thu thập evidence và viết notes | Query, audience, local sources | `sources`, `research_notes` |
| Analyst | Biến research notes thành insight có cấu trúc | Research notes, query, audience | `analysis_notes` |
| Writer | Viết câu trả lời cuối cùng cho người dùng | Research notes, analysis notes, sources | `final_answer` |
| Critic | Fact-check final answer, citation usage và unsupported claims | Final answer, sources, research notes, analysis notes | `critic_notes`, validation findings |

Sự tách vai trò này giúp tránh việc một agent vừa research, vừa phân tích, vừa viết final answer, vừa tự fact-check trong cùng một bước.

## 5. Thiết kế shared state

Workflow dùng `ResearchState` làm object handoff duy nhất. Các field quan trọng:

- `request`: query gốc, audience và max source count.
- `iteration`: số bước routing, dùng cho max-iteration guard.
- `route_history`: route thực tế của workflow.
- `sources`: danh sách tài liệu có thể cite.
- `research_notes`: output của Researcher.
- `analysis_notes`: output của Analyst.
- `final_answer`: output của Writer.
- `critic_notes`: output fact-check của Critic.
- `agent_results`: nội dung từng agent và metadata token/cost.
- `trace`: event-level execution trace.
- `errors`: lỗi runtime hoặc lý do fallback.

Shared state này đủ để debug agent nào đã chạy, agent đó tạo gì, tốn bao nhiêu token/cost, Critic phát hiện vấn đề nào và vì sao workflow dừng.

## 6. Guardrails

| Guardrail | Cách triển khai |
|---|---|
| Max iterations | `MAX_ITERATIONS=6` mặc định |
| Timeout | `TIMEOUT_SECONDS=60` mặc định |
| Retry | `LLMClient` retry OpenAI calls tối đa 3 lần với exponential backoff |
| Fallback | Workflow ghi errors và tạo fallback notes/answer nếu agent fail |
| Validation | Pydantic schemas validate state, sources, agent results và benchmark metrics |
| Local trace | Mỗi route và worker completion đều được ghi vào `state.trace` |
| Hosted trace | Trace đã được gửi lên LangSmith project `multi-agent-research-lab` |
| Bonus fact-check | Critic chạy sau Writer để kiểm tra final answer trước khi workflow `done` |

## 7. Kết quả kiểm tra

Các lệnh sau đã chạy thành công:

```text
python -m pytest
5 passed in 0.10s

python -m ruff check src tests
All checks passed!

python -m mypy src
Success: no issues found in 27 source files
```

Điều này xác nhận implementation pass unit tests, linting và strict type checking.

## 8. Kết quả benchmark

| Run | Latency (s) | Cost (USD) | Tokens | Citation coverage | Failure rate | Quality | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline-q1 | 13.60 | 0.0005 | 972 | N/A | 0% | 7.0 | completed |
| multi-agent-q1 | 32.28 | 0.0014 | 4949 | 20% | 0% | 8.5 | researcher > analyst > writer > critic > done |
| baseline-q2 | 9.49 | 0.0004 | 800 | N/A | 0% | 7.5 | completed |
| multi-agent-q2 | 32.60 | 0.0014 | 4925 | 100% | 0% | 9.0 | researcher > analyst > writer > critic > done |
| baseline-q3 | 8.38 | 0.0003 | 671 | N/A | 0% | 7.5 | completed |
| multi-agent-q3 | 30.13 | 0.0015 | 5305 | 100% | 0% | 9.0 | researcher > analyst > writer > critic > done |

So sánh trung bình:

| Metric | Single-agent avg | Multi-agent avg | Kết quả |
|---|---:|---:|---|
| Latency | 10.49s | 31.67s | Multi-agent chậm hơn khoảng 3.0 lần |
| Cost | 0.0004 USD | 0.0014 USD | Multi-agent tốn chi phí khoảng 3.6 lần |
| Tokens | 814 | 5060 | Multi-agent dùng khoảng 6.2 lần token |
| Citation coverage | N/A | 73.3% | Multi-agent đo được citation coverage |
| Failure rate | 0% | 0% | Cả hai cách đều hoàn thành thành công |

## 9. Phân tích benchmark

Baseline nhanh hơn và rẻ hơn vì chỉ dùng một lần gọi LLM. Output baseline đầy đủ, nhưng không expose research notes, analysis notes, citation coverage, critic notes hoặc route-level trace. Do đó baseline khó debug và khó review hơn.

Workflow multi-agent chậm hơn và tốn cost hơn vì dùng nhiều lần gọi LLM cho Researcher, Analyst, Writer và Critic. Tuy nhiên, cách này phù hợp hơn với bài lab vì thể hiện rõ role clarity, shared-state handoff, traceability, measurable citation behavior và fact-check trước khi kết thúc.

Kết quả multi-agent cho thấy tradeoff cụ thể:

- Query 1 có citation coverage 20%, vì Writer chủ yếu dùng nguồn Microsoft GraphRAG chính.
- Query 2 có citation coverage 100%.
- Query 3 có citation coverage 100%.

Điều quan trọng là Critic đã phát hiện vấn đề citation coverage thấp và các unsupported/overstated claims ở query 1. Vì vậy hệ thống không chỉ tạo answer, mà còn tự đánh dấu điểm yếu của answer.

## 10. Minh chứng LangSmith

Ngoài local JSON trace trong `reports/multi_agent_trace.json`, hệ thống đã gửi trace lên LangSmith.

Minh chứng gồm hai screenshot trong folder `reports`:

- [langsmith_run_list.png](langsmith_run_list.png): danh sách runs trong project `multi-agent-research-lab`, có run `multi_agent_workflow` thành công.
- [langsmith_run_tree.png](langsmith_run_tree.png): waterfall trace chi tiết của root run `multi_agent_workflow`.

Screenshot run tree cho thấy:

- Project: `multi-agent-research-lab`
- Root run: `multi_agent_workflow`
- View: Waterfall
- Child runs: `supervisor`, `researcher`, `supervisor`, `analyst`, `supervisor`, `writer`, `supervisor`, `critic`, `supervisor`
- Graph config hiển thị trong input: nodes gồm `supervisor`, `researcher`, `analyst`, `writer`, `critic`, `done`
- Guardrail hiển thị trong input: `max_iterations=6`, `timeout_seconds=60`

## 11. Giải thích trace

Trace đại diện cho query GraphRAG:

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

Các giá trị cụ thể từ local JSON trace:

- Route history: `researcher > analyst > writer > critic > done`
- Số iteration: 5
- Số sources thu thập: 5
- Researcher usage: 624 tokens, 0.00016605 USD
- Analyst usage: 719 tokens, 0.0002595 USD
- Writer usage: 1578 tokens, 0.0005598 USD
- Critic usage: 2043 tokens, 0.00045315 USD
- Citation coverage query GraphRAG: 20%
- Errors: không có

Giải thích:

1. Supervisor thấy thiếu `research_notes`, nên route sang Researcher.
2. Researcher chọn 5 sources và tạo evidence-backed notes.
3. Supervisor thấy thiếu `analysis_notes`, nên route sang Analyst.
4. Analyst chuyển notes thành thesis, key claims, tradeoffs, risks và confidence.
5. Supervisor route sang Writer vì research và analysis đã sẵn sàng.
6. Writer tạo final answer có citation.
7. Supervisor thấy đã có `final_answer`, nhưng chưa có `critic_notes`, nên route sang Critic.
8. Critic fact-check final answer dựa trên sources, research notes và analysis notes.
9. Supervisor thấy đã có `final_answer` và `critic_notes`, nên route sang `done`.

## 12. Critic findings

Critic đánh giá final answer của query GraphRAG là nhìn chung hữu ích nhưng còn một số claim chưa đủ evidence.

Các điểm Critic xác nhận:

- GraphRAG dùng graph-based indexes để hỗ trợ query-focused summarization.
- Việc kết hợp local/global context được source Microsoft Research hỗ trợ.
- Citation `[1]` khớp với source list.

Các điểm Critic cảnh báo:

- Citation coverage chỉ 20%.
- Claim “potentially outperforms traditional summarization methods” bị overstated vì không có comparative analysis hoặc performance metrics.
- Claim về practical real-world solution cần thêm ví dụ hoặc evidence.

Suggested fixes:

- Qualify hoặc bỏ claim so sánh nếu thiếu benchmark.
- Bổ sung source chuyên sâu hơn về GraphRAG.
- Giữ Critic như bước bắt buộc để flag unsupported claims.

## 13. Failure mode và cách sửa

Không có runtime failure trong benchmark. Failure mode chính quan sát được là **citation coverage chưa đầy đủ** ở query 1 và một số claim trong final answer vượt quá evidence.

Nguyên nhân:

- Source corpus có một nguồn GraphRAG trực tiếp, các nguồn còn lại thiên về agent workflow, orchestration và tracing.
- Writer tập trung vào source `[1]`, là nguồn GraphRAG liên quan nhất.
- Một số phrasing trong final answer mang tính so sánh nhưng không có performance metrics đi kèm.

Cách sửa:

- Siết prompt của Writer để tránh claim so sánh nếu không có benchmark evidence.
- Bổ sung live search hoặc thêm source GraphRAG chuyên sâu hơn.
- Giữ Critic thành bước bắt buộc sau Writer để fact-check final answer và citation usage.

## 14. Tự đánh giá theo peer review rubric

| Criterion | Target score | Evidence |
|---|---:|---|
| Role clarity | 2/2 | Supervisor, Researcher, Analyst, Writer, Critic có responsibility riêng |
| State design | 2/2 | Shared state có request, routes, sources, notes, final answer, critic notes, trace, errors, metadata |
| Failure guard | 2/2 | Có max iterations, timeout, retry, fallback, Pydantic validation |
| Benchmark | 2/2 | So sánh baseline vs multi-agent bằng latency, cost, tokens, citation coverage, failure rate, quality |
| Trace explanation | 2/2 | Local JSON trace và LangSmith waterfall giải thích được từng bước, bao gồm Critic |

## 15. Exit ticket

1. Nên dùng multi-agent khi task cần nhiều responsibility riêng, handoff rõ ràng, evidence tracking, fact-check hoặc nhiều giai đoạn như research, analysis và final writing.
2. Không nên dùng multi-agent khi task đơn giản, rủi ro thấp hoặc một prompt đã xử lý ổn, vì orchestration làm tăng latency, cost và độ phức tạp triển khai.

## 16. Kết luận

Hệ thống cuối cùng đáp ứng mục tiêu bài lab. Implementation dùng model OpenAI thật, có role rõ ràng, shared state, guardrails, local trace, LangSmith hosted trace, benchmark so sánh single-agent với multi-agent và bonus Critic fact-check. Kết quả benchmark xác nhận tradeoff dự kiến: multi-agent chậm hơn và đắt hơn, nhưng dễ inspect, debug, fact-check và đánh giá hơn đối với các research task phức tạp.
