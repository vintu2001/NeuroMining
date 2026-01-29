#!/usr/bin/env bash
# NeuroMining — Submit the MapReduce streaming job to Hadoop
# Run from inside the namenode container or with HADOOP_HOME configured.
set -euo pipefail

HADOOP_STREAMING_JAR="$(find "$HADOOP_HOME" -name 'hadoop-streaming-*.jar' | head -1)"

INPUT_PATH="hdfs:///neuromining/raw/clickstream/"
OUTPUT_PATH="hdfs:///neuromining/cleaned/session_counts/$(date +%Y%m%d_%H%M%S)"

echo "[run_job] Streaming JAR : $HADOOP_STREAMING_JAR"
echo "[run_job] Input         : $INPUT_PATH"
echo "[run_job] Output        : $OUTPUT_PATH"

# Upload local scripts to HDFS temp location (streaming -files distributes them)
hadoop fs -mkdir -p hdfs:///neuromining/tmp/scripts/

hadoop jar "$HADOOP_STREAMING_JAR" \
    -D mapreduce.job.name="NeuroMining-LogCleaning" \
    -D mapreduce.job.reduces=8 \
    -D mapreduce.map.memory.mb=2048 \
    -D mapreduce.reduce.memory.mb=2048 \
    -D stream.num.map.output.key.fields=2 \
    -D mapreduce.partition.keypartitioner.options="-k1,1" \
    -partitioner org.apache.hadoop.mapred.lib.KeyFieldBasedPartitioner \
    -files mapper.py,reducer.py \
    -mapper  "python3 mapper.py" \
    -reducer "python3 reducer.py" \
    -input   "$INPUT_PATH" \
    -output  "$OUTPUT_PATH"

echo "[run_job] Job complete. Output at: $OUTPUT_PATH"
echo "[run_job] Verifying record count …"
hadoop fs -cat "$OUTPUT_PATH/part-*" | wc -l
