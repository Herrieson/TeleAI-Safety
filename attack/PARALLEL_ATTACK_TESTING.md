# parallel_attack.py 测试使用文档

本文说明如何在 `TeleAI-Safety/attack` 目录下使用 `parallel_attack.py` 对单个攻击方法进行并行测试。

## 1. 脚本作用

`parallel_attack.py` 会做这些事：

1. 读取你的方法配置（YAML）和数据集（`json`/`jsonl`）。
2. 按 `--shards` 把数据切分成多个分片。
3. 为每个分片生成临时配置，并并发执行：
   `python <method.py> --config_path <临时配置>`
4. 收集分片结果与日志，输出耗时统计。
5. 当 `res_save_path` 为 `jsonl` 时，支持增量落盘和断点续跑。

## 2. 前置条件

在 `attack` 根目录执行：

```bash
cd /home/hyx/workplace/TeleAI-Safety/attack
```

确保以下条件满足：

1. 方法脚本存在，例如 `methods/pair.py`。
2. 配置文件存在，例如 `configs/gpt-5.4/pair.yaml`。
3. 配置里至少有一个数据路径键：
   - `attack_data_path` 或
   - `data_path` 或
   - `dataset_path`
4. 数据文件格式是 `json` 或 `jsonl`。
5. 方法脚本支持 `--config_path` 参数（仓库里的主流方法都支持）。

如果配置里用了环境变量（如 `${AZURE_OPENAI_API_KEY}`），需要先 `export` 对应变量。

## 3. 命令参数

`parallel_attack.py` 参数如下：

- `--method`（必填）：方法脚本路径，如 `methods/pair.py`
- `--config`（必填）：方法 YAML 配置路径
- `--shards`（必填）：数据分片数量
- `--max-workers`：并发 worker 数，默认等于 `shards`
- `--progress-interval`：进度打印间隔（秒），`0` 表示关闭，默认 `15`
- `--save-interval`：增量写回间隔（秒），`0` 表示关闭，默认 `60`
- `--keep-temp`：保留临时分片文件和日志目录

## 4. 最小测试（推荐先做）

先对单个方法做小规模验证：

```bash
uv run python parallel_attack.py \
  --method methods/pair.py \
  --config configs/gpt-5.4/pair.yaml \
  --shards 4 \
  --max-workers 4 \
  --progress-interval 10 \
  --save-interval 30
```

说明：

1. `shards` 建议先设为 `2~4` 验证流程。
2. `res_save_path` 建议使用 `.jsonl`，这样才能稳定增量保存与续跑。
3. 成功后会输出 `[timing] ...` 并在结果目录生成 `<method>.timing.json`。

## 5. 断点续跑与增量保存

当配置包含 `res_save_path: xxx.jsonl` 时：

1. 启动时会读取已有结果，自动跳过已完成样本（基于 `id/example_id/sample_id/uid/query` 匹配）。
2. 运行中会按 `--save-interval` 将各分片新增结果合并写回主结果文件。
3. 中断后重新执行同一命令，会从剩余样本继续。

如果看到日志：

```text
[resume] skipped N completed records ...
```

表示续跑机制已生效。

## 6. 日志与产物位置

1. 分片日志：临时目录下 `shard_<i>.log`
2. 分片结果：临时目录下 `res_shard_<i>.*`
3. 汇总结果：配置中的 `res_save_path`
4. 耗时统计：`<res_save_path目录>/<method名>.timing.json`

默认成功后会删除临时目录；排查问题时加 `--keep-temp` 保留现场。

## 7. 常见问题排查

1. 报错 `Missing dataset path in config...`
   - 配置缺少 `attack_data_path/data_path/dataset_path`。
2. 报错 `Unsupported data file type`
   - 输入数据不是 `json/jsonl`。
3. 报错 `One or more shards failed`
   - 至少一个分片子进程失败，查看对应 `shard_<i>.log`。
4. 结果文件是 `.json` 且内容异常
   - 并行聚合更推荐使用 `.jsonl`；`json` 在多分片场景不如 `jsonl` 稳定。

## 8. 推荐测试流程

1. 先跑小分片（`shards=2~4`）确认配置与鉴权正确。
2. 观察 `res_save_path` 是否持续增长、日志是否有异常回溯。
3. 中断后重跑一次，确认 `[resume]` 生效。
4. 再放大到正式并发参数（例如 `shards=8/16`）。
