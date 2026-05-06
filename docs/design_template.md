# Design Template

## Problem

Hệ thống cần xử lý các truy vấn nghiên cứu dài của người dùng, thu thập nguồn liên quan, phân tích bằng chứng, viết câu trả lời cuối cùng có citation và kiểm tra lại câu trả lời trước khi kết thúc. Bài lab yêu cầu so sánh **single-agent baseline** với **multi-agent workflow** theo các metric cụ thể như latency, cost, token usage, citation coverage, failure rate và quality.

## Why multi-agent?

Single-agent nhanh và đơn giản, nhưng dễ bị quá tải vì phải làm nhiều việc trong cùng một prompt: tìm nguồn, đánh giá bằng chứng, phân tích tradeoff, viết câu trả lời và tự kiểm tra lỗi. Multi-agent phù hợp hơn cho bài lab này vì:

- Mỗi agent có một responsibility riêng, giúp giảm overlap và dễ debug.
- Shared state lưu rõ từng artifact trung gian: sources, research notes, analysis notes, final answer, critic notes, route history và errors.
- Supervisor điều phối route theo rule deterministic nên trace dễ giải thích.
- Workflow có guardrails: max iterations, timeout, retry, fallback và validation.
- Benchmark đo được tradeoff giữa chất lượng, cost, latency và citation coverage.
- Critic agent tạo thêm bước fact-check để phát hiện unsupported claims và citation issues.

## Agent roles

| Agent | Responsibility | Input | Output | Failure mode |
|---|---|---|---|---|
| Supervisor | Kiểm tra shared state và chọn route tiếp theo: researcher, analyst, writer, critic hoặc done | `ResearchState` gồm query, notes, final answer, critic notes, errors, iteration | Cập nhật `route_history`, `iteration`, trace và `AgentResult` | Sai route, lặp quá nhiều, hoặc bỏ qua bước cần thiết |
| Researcher | Thu thập sources và tạo research notes có citation | Query, audience, `max_sources`, local source corpus | `sources`, `research_notes`, trace token/cost | Source chưa đủ liên quan, notes thiếu evidence, LLM/API fail |
| Analyst | Biến research notes thành thesis, key claims, tradeoffs, risks và confidence | Query, audience, research notes, sources | `analysis_notes`, trace token/cost | Phân tích quá chung chung, claim vượt quá evidence, mất citation |
| Writer | Viết final answer từ research notes, analysis notes và sources | Query, audience, research notes, analysis notes, sources | `final_answer`, trace token/cost | Hallucination, citation thiếu, phrasing quá mạnh so với evidence |
| Critic | Fact-check final answer, citation usage và unsupported claims | Final answer, sources, research notes, analysis notes | `critic_notes`, citation coverage, fact-check findings | Quá nghiêm khắc, cảnh báo thiếu evidence khi source corpus còn hạn chế |

## Shared state

Workflow dùng `ResearchState` làm object handoff duy nhất:

- `request`: query gốc, audience và `max_sources`.
- `iteration`: số lần Supervisor route, dùng để enforce `MAX_ITERATIONS`.
- `route_history`: trace ngắn của orchestration, ví dụ `researcher > analyst > writer > critic > done`.
- `sources`: danh sách `SourceDocument` để Writer cite và benchmark citation coverage.
- `research_notes`: output của Researcher, làm input chính cho Analyst.
- `analysis_notes`: output của Analyst, làm input chính cho Writer.
- `final_answer`: output chính cho người dùng.
- `critic_notes`: output fact-check của Critic.
- `agent_results`: output từng agent kèm metadata token/cost.
- `trace`: event log gồm workflow start, route decision, worker completion và workflow completion.
- `errors`: lỗi runtime hoặc fallback reason để tính failure rate và giải thích failure mode.

## Routing policy

Graph dạng state machine:

```text
START
  |
  v
Supervisor
  |-- nếu thiếu research_notes --> Researcher --> Supervisor
  |-- nếu thiếu analysis_notes --> Analyst ----> Supervisor
  |-- nếu thiếu final_answer ----> Writer -----> Supervisor
  |-- nếu thiếu critic_notes ----> Critic -----> Supervisor
  |-- nếu đã có final_answer
      và critic_notes ---------> DONE
```

Supervisor dùng routing policy deterministic:

1. Nếu `iteration >= MAX_ITERATIONS`:
   - Nếu chưa có `final_answer`, route sang `writer`.
   - Nếu đã có `final_answer` nhưng chưa có `critic_notes`, route sang `critic`.
   - Nếu đã có cả `final_answer` và `critic_notes`, route sang `done`.
2. Nếu đã có `final_answer` và `critic_notes`, route sang `done`.
3. Nếu đã có `final_answer` nhưng chưa có `critic_notes`, route sang `critic`.
4. Nếu thiếu `research_notes`, route sang `researcher`.
5. Nếu thiếu `analysis_notes`, route sang `analyst`.
6. Còn lại route sang `writer`.

Route kỳ vọng:

```text
researcher > analyst > writer > critic > done
```

## Guardrails

- **Max iterations**: dùng `MAX_ITERATIONS`, mặc định là 6.
- **Timeout**: dùng `TIMEOUT_SECONDS`, mặc định là 60 giây cho workflow.
- **Retry**: `LLMClient` retry OpenAI call tối đa 3 lần với exponential backoff.
- **Fallback**: workflow ghi `errors` và tạo fallback notes/answer/critic notes nếu agent fail.
- **Validation**: Pydantic schema validate input/output chính như `ResearchQuery`, `ResearchState`, `SourceDocument`, `AgentResult`, `BenchmarkMetrics`.
- **Trace**: local JSON trace trong `ResearchState.trace` và hosted trace trên LangSmith.
- **Fact-check**: Critic kiểm tra final answer dựa trên sources, research notes và analysis notes.

## Benchmark plan

| Query | Metric | Expected outcome |
|---|---|---|
| Research GraphRAG state-of-the-art and write a 500-word summary | Latency, cost, tokens, citation coverage, failure rate, quality | Multi-agent chậm hơn và tốn token hơn baseline, nhưng có trace rõ hơn và Critic phát hiện claim/citation yếu |
| Compare single-agent and multi-agent workflows for customer support | Latency, cost, quality, citation coverage | Multi-agent giải thích tradeoff, route và failure mode tốt hơn |
| Summarize production guardrails for LLM agents | Citation coverage, quality, trace explanation | Multi-agent thể hiện guardrails rõ hơn nhờ Researcher, Analyst, Writer và Critic |

Quality được đánh giá theo rubric 0-10:

- Role clarity: 0-2
- State design: 0-2
- Failure guard: 0-2
- Benchmark: 0-2
- Trace explanation: 0-2

Kết quả benchmark mới sau khi thêm Critic:

| Run | Latency (s) | Cost (USD) | Tokens | Citation coverage | Failure rate |
|---|---:|---:|---:|---:|---:|
| baseline-q1 | 13.60 | 0.0005 | 972 | N/A | 0% |
| multi-agent-q1 | 32.28 | 0.0014 | 4949 | 20% | 0% |
| baseline-q2 | 9.49 | 0.0004 | 800 | N/A | 0% |
| multi-agent-q2 | 32.60 | 0.0014 | 4925 | 100% | 0% |
| baseline-q3 | 8.38 | 0.0003 | 671 | N/A | 0% |
| multi-agent-q3 | 30.13 | 0.0015 | 5305 | 100% | 0% |

## Trace evidence

Trace được lưu ở hai nơi:

- Local JSON: `reports/multi_agent_trace.json`
- LangSmith screenshots:
  - `reports/langsmith_run_list.png`
  - `reports/langsmith_run_tree.png`

LangSmith waterfall thể hiện root run `multi_agent_workflow` và các child runs:

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
