# Báo Cáo Benchmark

## Tóm Tắt

Báo cáo này ghi nhận lần benchmark mới nhất sau khi tích hợp Tavily live search và siết prompt của `WriterAgent` để bắt buộc citation cho các claim quan trọng.

Hệ thống so sánh hai chế độ:

- **Single-agent baseline**: một lần gọi OpenAI `gpt-4o-mini` để xử lý toàn bộ truy vấn.
- **Multi-agent workflow**: Supervisor điều phối `Researcher -> Analyst -> Writer -> Critic -> done`.

## Kết Quả Benchmark Mới Nhất

| Run | Latency (s) | Cost (USD) | Tokens | Citation coverage | Failure rate | Quality | Ghi chú |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline-q1 | 14.99 | 0.0005 | 994 | N/A | 0% | 7.0 | completed |
| multi-agent-q1 | 30.28 | 0.0020 | 7588 | 80% | 0% | 8.5 | researcher > analyst > writer > critic > done |
| baseline-q2 | 12.40 | 0.0004 | 746 | N/A | 0% | 7.5 | completed |
| multi-agent-q2 | 25.36 | 0.0018 | 7378 | 60% | 0% | 8.5 | researcher > analyst > writer > critic > done |
| baseline-q3 | 14.24 | 0.0004 | 736 | N/A | 0% | 7.5 | completed |
| multi-agent-q3 | 25.36 | 0.0019 | 7845 | 100% | 0% | 9.0 | researcher > analyst > writer > critic > done |

## Trung Bình

| Metric | Single-agent avg | Multi-agent avg | Nhận xét |
|---|---:|---:|---|
| Latency | 13.88s | 27.00s | Multi-agent chậm hơn khoảng 1.9 lần |
| Cost | 0.0004 USD | 0.0019 USD | Multi-agent tốn chi phí khoảng 4.8 lần |
| Tokens | 825 | 7604 | Multi-agent dùng nhiều token hơn do có live sources và nhiều agent |
| Citation coverage | N/A | 80.0% | Coverage tăng rõ sau khi siết Writer prompt |
| Failure rate | 0% | 0% | Không có runtime failure |

## Phân Tích

Baseline vẫn nhanh và rẻ hơn vì chỉ gọi một LLM. Tuy nhiên, baseline thiếu observability: không có research notes, không có source list có cấu trúc, không có route history và không có Critic fact-check.

Multi-agent chậm hơn và tốn nhiều token hơn, nhưng phù hợp với yêu cầu bài lab hơn. Workflow có role clarity, shared-state handoff, LangSmith trace, local run logs và Critic để kiểm tra citation/unsupported claims.

Sau khi thêm Tavily, Researcher lấy được nguồn live thay vì chỉ dựa vào local corpus. Sau khi siết prompt Writer, q3 citation coverage tăng từ 0% lên 100%. Điều này cho thấy failure mode trước đó không phải lỗi workflow, mà là lỗi prompt: Writer cần được yêu cầu rõ ràng rằng từng claim quan trọng phải có citation.

q2 giảm còn 60% citation coverage. Critic vẫn phát hiện được vấn đề này, nên đây là điểm cần cải thiện tiếp: tiếp tục siết Writer để citation được rải đều hơn trong từng paragraph/bullet, không chỉ tập trung ở một vài đoạn.

## Trace Và Log

Trace được ghi ở ba nơi:

- `reports/multi_agent_trace.json`: trace đại diện mới nhất cho query GraphRAG trong benchmark Tavily.
- `runs/baseline/*.json`: local log cho từng lần chạy baseline.
- `runs/multi-agent/*.json`: local log cho từng lần chạy multi-agent.

LangSmith hosted trace nằm trên website LangSmith, trong project `multi-agent-research-lab`.

Ảnh minh chứng:

- `reports/langsmith_run_list.png`
- `reports/langsmith_run_tree.png`

LangSmith span hiện có input/output đầy đủ:

- `researcher`: output có Tavily `sources` và `research_notes`.
- `analyst`: input có research notes, output có `analysis_notes`.
- `writer`: input có sources, research notes, analysis notes; output có `final_answer`.
- `critic`: input có final answer và evidence; output có `critic_notes`.

## Trace GraphRAG Đại Diện

Run đại diện trong `reports/multi_agent_trace.json`:

- Query: `Research GraphRAG state-of-the-art and write a 500-word summary`
- Route: `researcher > analyst > writer > critic > done`
- Source count: 5
- Source provider: Tavily
- Citation coverage: 80%
- Errors: 0

Token/cost theo agent:

| Agent | Tokens | Cost (USD) |
|---|---:|---:|
| Researcher | 1602 | 0.0004257 |
| Analyst | 997 | 0.00031335 |
| Writer | 1952 | 0.00057675 |
| Critic | 3037 | 0.000636 |

## Failure Mode

Không có lỗi runtime trong benchmark mới nhất. Failure mode chính còn lại là citation coverage chưa đồng đều:

- q1: 80%, tốt nhưng vẫn còn một số claim chưa cite.
- q2: 60%, cần cải thiện prompt hoặc post-check để Writer rải citation đều hơn.
- q3: 100%, đã sửa được lỗi thiếu citation của lần chạy trước.

Cách cải thiện tiếp theo là thêm bước sửa sau Critic: nếu Critic phát hiện citation coverage thấp, workflow có thể route ngược lại Writer để revise final answer trước khi `done`.
