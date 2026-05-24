import 'package:flutter/material.dart';

import '../models.dart';
import '../utils.dart';

class ResultsPanel extends StatelessWidget {
  const ResultsPanel({
    super.key,
    required this.runState,
    required this.progress,
    required this.summary,
    required this.currentKey,
    required this.currentTitle,
    required this.results,
    required this.logs,
    required this.logPath,
    required this.onOpenMarkdown,
    required this.onOpenCsv,
    required this.onOpenOutputDir,
    required this.onOpenLog,
    required this.onCopyLogs,
  });

  final RunState runState;
  final double progress;
  final RunSummary summary;
  final String currentKey;
  final String currentTitle;
  final List<EntryResult> results;
  final List<String> logs;
  final String logPath;
  final VoidCallback onOpenMarkdown;
  final VoidCallback onOpenCsv;
  final VoidCallback onOpenOutputDir;
  final VoidCallback onOpenLog;
  final VoidCallback onCopyLogs;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: const BorderSide(color: Color(0xffd9ded6)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Expanded(
                  child: Text(
                    '结果',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                  ),
                ),
                StateChip(runState: runState),
              ],
            ),
            const SizedBox(height: 14),
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: runState == RunState.running && summary.total == 0
                    ? null
                    : progress,
                minHeight: 10,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              currentKey.isEmpty
                  ? '等待开始'
                  : '$currentKey  ${trimStr(currentTitle, 110)}',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                MetricCard(label: '总数', value: summary.total),
                MetricCard(label: '找到', value: summary.found),
                MetricCard(label: '未找到', value: summary.notFound),
                MetricCard(label: '需人工核查', value: summary.needsReview),
                MetricCard(label: '跳过', value: summary.skipped),
                MetricCard(label: '作者问题', value: summary.authorMismatch),
                MetricCard(label: '年份问题', value: summary.yearMismatch),
                MetricCard(label: 'DOI 问题', value: summary.doiMismatch),
              ],
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton.icon(
                  onPressed:
                      summary.markdownPath.isEmpty ? null : onOpenMarkdown,
                  icon: const Icon(Icons.description_outlined),
                  label: const Text('Markdown'),
                ),
                FilledButton.tonalIcon(
                  onPressed: summary.csvPath.isEmpty ? null : onOpenCsv,
                  icon: const Icon(Icons.table_chart_outlined),
                  label: const Text('CSV'),
                ),
                OutlinedButton.icon(
                  onPressed: summary.outputDir.isEmpty ? null : onOpenOutputDir,
                  icon: const Icon(Icons.folder_open_rounded),
                  label: const Text('目录'),
                ),
                OutlinedButton.icon(
                  onPressed: logPath.isEmpty ? null : onOpenLog,
                  icon: const Icon(Icons.article_outlined),
                  label: const Text('日志'),
                ),
                OutlinedButton.icon(
                  onPressed: logs.isEmpty ? null : onCopyLogs,
                  icon: const Icon(Icons.copy_rounded),
                  label: const Text('复制日志'),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Expanded(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Expanded(
                    child: ResultList(results: results),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: LogList(logs: logs),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class StateChip extends StatelessWidget {
  const StateChip({super.key, required this.runState});

  final RunState runState;

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (runState) {
      RunState.idle => ('待开始', const Color(0xff687269)),
      RunState.running => ('运行中', const Color(0xff1f7a6d)),
      RunState.completed => ('已完成', const Color(0xff276b37)),
      RunState.failed => ('失败', const Color(0xffa23a33)),
    };
    return Chip(
      label: Text(label),
      avatar: Icon(Icons.circle, color: color, size: 12),
      visualDensity: VisualDensity.compact,
    );
  }
}

class MetricCard extends StatelessWidget {
  const MetricCard({super.key, required this.label, required this.value});

  final String label;
  final int value;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 108,
      height: 78,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.white,
          border: Border.all(color: const Color(0xffd9ded6)),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, maxLines: 1, overflow: TextOverflow.ellipsis),
              const Spacer(),
              Text(
                '$value',
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class ResultList extends StatelessWidget {
  const ResultList({super.key, required this.results});

  final List<EntryResult> results;

  @override
  Widget build(BuildContext context) {
    return PanelFrame(
      title: '条目',
      child: results.isEmpty
          ? const Center(child: Text('暂无条目'))
          : ListView.separated(
              itemCount: results.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final item = results[index];
                return ListTile(
                  dense: true,
                  leading: Icon(
                    _statusIcon(item),
                    color: item.status == 'found' && !item.needsReview
                        ? const Color(0xff276b37)
                        : item.status == 'found' || item.needsReview
                            ? const Color(0xffb54708)
                            : const Color(0xffb42318),
                  ),
                  title: RichText(
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    text: TextSpan(
                      style: DefaultTextStyle.of(context).style,
                      children: [
                        TextSpan(text: item.key),
                        TextSpan(text: ' · 置信度 ${item.confidenceScore}'),
                      ],
                    ),
                  ),
                  subtitle: Text(
                    trimStr(_subtitle(item), 130),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing: Text(_statusLabel(item)),
                );
              },
            ),
    );
  }

  IconData _statusIcon(EntryResult item) {
    if (item.status == 'found' && !item.needsReview) {
      return Icons.check_circle_outline_rounded;
    }
    if (item.status == 'found' || item.needsReview) {
      return Icons.error_outline_rounded;
    }
    if (item.status == 'skipped') {
      return Icons.skip_next_outlined;
    }
    return Icons.cancel_outlined;
  }

  String _subtitle(EntryResult item) {
    final title = item.title.isEmpty ? item.reason : item.title;
    if (item.suggestedAction.isEmpty || item.suggestedAction == '无需处理。') {
      return title;
    }
    return '$title｜建议：${item.suggestedAction}';
  }

  String _statusLabel(EntryResult item) {
    final source = item.source.isEmpty ? item.status : item.source;
    final sim =
        item.similarity == null ? '' : ' ${(item.similarity! * 100).round()}%';
    return '$source$sim';
  }
}

class LogList extends StatelessWidget {
  const LogList({super.key, required this.logs});

  final List<String> logs;

  @override
  Widget build(BuildContext context) {
    return PanelFrame(
      title: '日志',
      child: logs.isEmpty
          ? const Center(child: Text('暂无日志'))
          : ListView.separated(
              reverse: true,
              itemCount: logs.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, index) {
                return Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  child: SelectableText(logs[index]),
                );
              },
            ),
    );
  }
}

class PanelFrame extends StatelessWidget {
  const PanelFrame({super.key, required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: const Color(0xffd9ded6)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
            child: Text(title,
                style: const TextStyle(fontWeight: FontWeight.w700)),
          ),
          const Divider(height: 1),
          Expanded(child: child),
        ],
      ),
    );
  }
}
