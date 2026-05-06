# Báo Cáo Benchmark

## Tóm Tắt

Báo cáo này so sánh hai cách chạy của hệ thống research assistant:

- **Single-agent baseline**: một lần gọi OpenAI `gpt-4o-mini` xử lý toàn bộ truy vấn.
- **Multi-agent workflow**: Supervisor điều phối qua `Researcher -> Analyst -> Writer -> Critic -> done`.

Lần chạy benchmark mới nhất tạo log trong `runs/baseline/` và `runs/multi-agent/`. Hệ thống cũng ghi trace lên LangSmith project `multi-agent-research-lab`.

## Kết Quả Benchmark Mới Nhất

| Run | Latency (s) | Cost (USD) | Tokens | Citation coverage | Failure rate | Quality | Ghi chú |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline-q1 | 14.02 | 0.0005 | 932 | N/A | 0% | 7.0 | completed |
| multi-agent-q1 | 29.68 | 0.0013 | 4699 | 20% | 0% | 8.5 | researcher > analyst > writer > critic > done |
| baseline-q2 | 11.51 | 0.0004 | 762 | N/A | 0% | 7.5 | completed |
| multi-agent-q2 | 28.75 | 0.0014 | 5021 | 100% | 0% | 9.0 | researcher > analyst > writer > critic > done |
| baseline-q3 | 12.92 | 0.0004 | 707 | N/A | 0% | 7.5 | completed |
| multi-agent-q3 | 33.01 | 0.0014 | 5140 | 100% | 0% | 9.0 | researcher > analyst > writer > critic > done |

## Trung Bình

| Metric | Single-agent avg | Multi-agent avg | Nhận xét |
|---|---:|---:|---|
| Latency | 12.82s | 30.48s | Multi-agent chậm hơn khoảng 2.4 lần |
| Cost | 0.0004 USD | 0.0014 USD | Multi-agent tốn chi phí khoảng 3.2 lần |
| Tokens | 800 | 4953 | Multi-agent dùng nhiều token hơn do có nhiều agent |
| Citation coverage | N/A | 73.3% | Multi-agent đo được citation coverage nhờ Critic |
| Failure rate | 0% | 0% | Cả hai chế độ đều hoàn thành thành công |

## Phân Tích

Baseline nhanh hơn và rẻ hơn vì chỉ gọi một LLM cho toàn bộ tác vụ. Tuy nhiên, baseline không có research notes, analysis notes, critic notes, route history hay citation coverage nên khó kiểm tra chất lượng từng bước.

Multi-agent có latency, token và cost cao hơn vì chạy nhiều node. Đổi lại, workflow thể hiện rõ vai trò của từng agent, có handoff qua shared state, có trace từng bước, có local run logs và có Critic để fact-check final answer. Đây là tradeoff phù hợp với bài lab vì yêu cầu không chỉ là tạo câu trả lời, mà còn phải giải thích được quá trình tạo câu trả lời.

Query GraphRAG có citation coverage thấp nhất, chỉ 20%, vì Writer chủ yếu dựa vào nguồn Microsoft GraphRAG trực tiếp. Critic đã phát hiện điểm này và cảnh báo các claim hơi mạnh như “significantly enhances” hoặc “powerful tool” khi chưa có comparative metrics. Đây là minh chứng cho giá trị của Critic: hệ thống tự đánh dấu điểm yếu thay vì chỉ trả lời một chiều.

## Trace Và Log

Trace được ghi ở ba nơi:

- `reports/multi_agent_trace.json`: trace đại diện mới nhất cho query GraphRAG.
- `runs/baseline/*.json`: local log cho từng lần chạy baseline.
- `runs/multi-agent/*.json`: local log cho từng lần chạy multi-agent.

LangSmith hosted trace nằm trên website LangSmith, trong workspace cá nhân và project `multi-agent-research-lab`. Hai ảnh minh chứng đã được lưu trong folder `reports`:

- `reports/langsmith_run_list.png`: danh sách run trong project.
- `reports/langsmith_run_tree.png`: waterfall trace của `multi_agent_workflow`.

Sau lần sửa mới nhất, các span trên LangSmith đã có input/output đầy đủ hơn:

- `researcher` output có `research_notes` và `sources`.
- `analyst` input có `research_notes`, output có `analysis_notes`.
- `writer` input có `research_notes`, `analysis_notes`, `sources`, output có `final_answer`.
- `critic` input có `final_answer` và evidence, output có `critic_notes`.

## Failure Mode

Không có runtime failure trong benchmark mới nhất. Failure mode chính là chất lượng evidence chưa đồng đều:

- Query 1 có citation coverage thấp.
- Một số claim của Writer cần được qualify kỹ hơn.
- Source corpus hiện tại có một nguồn GraphRAG trực tiếp, các nguồn còn lại thiên về agent workflow, orchestration và tracing.

Cách cải thiện tiếp theo là mở rộng source corpus hoặc thêm live search để Researcher có nhiều nguồn GraphRAG chuyên sâu hơn.
