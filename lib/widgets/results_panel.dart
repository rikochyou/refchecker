import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

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
        child: DefaultTabController(
          length: 6,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  const Expanded(
                    child: Text(
                      '结果',
                      style:
                          TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
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
              const SizedBox(height: 14),
              SummaryStrip(summary: summary),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed:
                        summary.markdownPath.isEmpty ? null : onOpenMarkdown,
                    icon: const Icon(Icons.description_outlined),
                    label: const Text('报告'),
                  ),
                  FilledButton.tonalIcon(
                    onPressed: summary.csvPath.isEmpty ? null : onOpenCsv,
                    icon: const Icon(Icons.table_chart_outlined),
                    label: const Text('CSV'),
                  ),
                  OutlinedButton.icon(
                    onPressed:
                        summary.outputDir.isEmpty ? null : onOpenOutputDir,
                    icon: const Icon(Icons.folder_open_rounded),
                    label: const Text('目录'),
                  ),
                  OutlinedButton.icon(
                    onPressed: logPath.isEmpty ? null : onOpenLog,
                    icon: const Icon(Icons.article_outlined),
                    label: const Text('日志文件'),
                  ),
                  OutlinedButton.icon(
                    onPressed: logs.isEmpty ? null : onCopyLogs,
                    icon: const Icon(Icons.copy_rounded),
                    label: const Text('复制日志'),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              const TabBar(
                isScrollable: true,
                tabs: [
                  Tab(icon: Icon(Icons.list_alt_rounded), text: '核验结果'),
                  Tab(icon: Icon(Icons.psychology_alt_outlined), text: '风险解释'),
                  Tab(icon: Icon(Icons.build_circle_outlined), text: '修复建议'),
                  Tab(icon: Icon(Icons.format_quote_outlined), text: '规范引用'),
                  Tab(icon: Icon(Icons.schema_outlined), text: '正文一致性'),
                  Tab(icon: Icon(Icons.article_outlined), text: '日志'),
                ],
              ),
              const SizedBox(height: 8),
              Expanded(
                child: TabBarView(
                  children: [
                    ResultList(results: results),
                    RiskExplanationView(results: results, summary: summary),
                    FixSuggestionView(results: results),
                    CitationFormatView(results: results),
                    ConsistencyView(summary: summary),
                    LogList(logs: logs),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class SummaryStrip extends StatelessWidget {
  const SummaryStrip({super.key, required this.summary});

  final RunSummary summary;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        MetricPill(label: '总数', value: summary.total),
        MetricPill(label: '找到', value: summary.found),
        MetricPill(label: '未找到', value: summary.notFound),
        MetricPill(label: '高风险', value: summary.highRisk),
        MetricPill(label: '中风险', value: summary.mediumRisk),
        MetricPill(label: '人工核查', value: summary.needsReview),
        MetricPill(label: 'DOI 问题', value: summary.doiMismatch),
      ],
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

class MetricPill extends StatelessWidget {
  const MetricPill({super.key, required this.label, required this.value});

  final String label;
  final int value;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 34,
      padding: const EdgeInsets.symmetric(horizontal: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: const Color(0xffd9ded6)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: const TextStyle(color: Color(0xff596158))),
          const SizedBox(width: 8),
          Text(
            '$value',
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
        ],
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
                  onTap: () => _showEntryDetail(context, item),
                  leading: Icon(
                    _statusIcon(item),
                    color: _statusColor(item),
                  ),
                  title: Text(
                    '${item.key} · 置信度 ${item.confidenceScore}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: Text(
                    trimStr(_subtitle(item), 150),
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

  Color _statusColor(EntryResult item) {
    if (item.status == 'found' && !item.needsReview) {
      return const Color(0xff276b37);
    }
    if (item.status == 'found' || item.needsReview) {
      return const Color(0xffb54708);
    }
    return const Color(0xffb42318);
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

  void _showEntryDetail(BuildContext context, EntryResult item) {
    showDialog<void>(
      context: context,
      builder: (ctx) => EntryDetailDialog(item: item),
    );
  }
}

class RiskExplanationView extends StatelessWidget {
  const RiskExplanationView({
    super.key,
    required this.results,
    required this.summary,
  });

  final List<EntryResult> results;
  final RunSummary summary;

  @override
  Widget build(BuildContext context) {
    final priority = results
        .where((item) => item.riskLevel == 'high' || item.riskLevel == 'medium')
        .toList();
    return PanelFrame(
      title: '风险解释',
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          if (summary.reportSummary.isNotEmpty) ...[
            InfoBox(
              icon: Icons.summarize_outlined,
              title: '规则报告摘要',
              text: summary.reportSummary,
            ),
            const SizedBox(height: 12),
          ],
          const SizedBox(height: 12),
          if (priority.isEmpty)
            const Center(
                child: Padding(
              padding: EdgeInsets.all(24),
              child: Text('暂无中高风险条目'),
            ))
          else
            for (final item in priority)
              ExplanationTile(
                icon: Icons.psychology_alt_outlined,
                title: '${item.key} · ${_riskLabel(item.riskLevel)}',
                subtitle: item.source,
                body: item.riskExplanation,
              ),
        ],
      ),
    );
  }
}

class FixSuggestionView extends StatelessWidget {
  const FixSuggestionView({super.key, required this.results});

  final List<EntryResult> results;

  @override
  Widget build(BuildContext context) {
    final actionable = results
        .where((item) =>
            item.fixSuggestion.isNotEmpty ||
            item.suggestedAction != '无需处理。')
        .toList();
    return PanelFrame(
      title: '修复建议',
      child: actionable.isEmpty
          ? const Center(child: Text('暂无需要修复的条目'))
          : ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: actionable.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (context, index) {
                final item = actionable[index];
                return ExplanationTile(
                  icon: Icons.build_circle_outlined,
                  title: item.key,
                  subtitle: item.title,
                  body: _withOptionalBasis(
                    item.fixSuggestion.isNotEmpty
                        ? item.fixSuggestion
                        : item.suggestedAction,
                    item.fixSuggestionBasis,
                  ),
                );
              },
            ),
    );
  }
}

class CitationFormatView extends StatelessWidget {
  const CitationFormatView({super.key, required this.results});

  final List<EntryResult> results;

  @override
  Widget build(BuildContext context) {
    final available =
        results.where((item) => item.standardCitationAvailable).toList();
    return PanelFrame(
      title: '规范引用',
      child: available.isEmpty
          ? const Center(child: Text('暂无可生成的规范引用；未匹配条目不会被补造。'))
          : ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: available.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (context, index) {
                final item = available[index];
                return DetailSection(
                  title: item.key,
                  children: [
                    if (item.standardCitationBasis.isNotEmpty)
                      SelectableText('依据：${item.standardCitationBasis}'),
                    CitationBlock(
                        label: 'APA', value: item.standardCitationApa),
                    CitationBlock(
                        label: 'BibTeX', value: item.standardCitationBibtex),
                    CitationBlock(
                        label: 'GB/T 7714',
                        value: item.standardCitationGbt7714),
                  ],
                );
              },
            ),
    );
  }
}

class ConsistencyView extends StatelessWidget {
  const ConsistencyView({super.key, required this.summary});

  final RunSummary summary;

  @override
  Widget build(BuildContext context) {
    final hasResult = summary.citationConsistencyPath.isNotEmpty;
    return PanelFrame(
      title: '正文引用一致性',
      child: !hasResult
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                    'DOCX 或包含 References / 参考文献标题的 TXT 会自动运行正文一致性检查；BibTeX 文件不包含正文，因此不会运行。'),
              ),
            )
          : FutureBuilder<Map<String, dynamic>>(
              future: _loadConsistency(summary.citationConsistencyPath),
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError || snapshot.data == null) {
                  return Center(child: Text('读取正文一致性结果失败：${snapshot.error}'));
                }
                final data = snapshot.data!;
                final available = data['available'] == true;
                if (!available) {
                  return ListView(
                    padding: const EdgeInsets.all(12),
                    children: [
                      InfoBox(
                        icon: Icons.schema_outlined,
                        title: '未运行正文一致性检查',
                        text: asText(data['reason']).isEmpty
                            ? '当前输入不包含正文。'
                            : asText(data['reason']),
                      ),
                    ],
                  );
                }
                return ListView(
                  padding: const EdgeInsets.all(12),
                  children: [
                    InfoBox(
                      icon: Icons.schema_outlined,
                      title: '检查方法',
                      text: asText(data['method']).isEmpty
                          ? '本地规则：提取正文作者-年份引用并与参考文献列表比对。'
                          : asText(data['method']),
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        MetricPill(
                            label: '正文缺失参考',
                            value: listOf(data['missing_references']).length),
                        MetricPill(
                            label: '未引用条目',
                            value: listOf(data['uncited_references']).length),
                        MetricPill(
                            label: '重复签名',
                            value:
                                listOf(data['duplicate_reference_signatures'])
                                    .length),
                      ],
                    ),
                    const SizedBox(height: 12),
                    JsonTableSection(
                      title: '正文引用缺少对应参考文献',
                      rows: listOf(data['missing_references']),
                      columns: const [
                        'citation',
                        'count',
                        'paragraph',
                        'context'
                      ],
                      labels: const ['正文引用', '次数', '段落', '上下文'],
                    ),
                    JsonTableSection(
                      title: '参考文献列表中可能未被正文引用',
                      rows: listOf(data['uncited_references']),
                      columns: const ['citation', 'key', 'paragraph', 'title'],
                      labels: const ['参考签名', 'Key', '段落', '标题'],
                    ),
                    JsonTableSection(
                      title: '同作者同年份重复签名',
                      rows: listOf(data['duplicate_reference_signatures']),
                      columns: const ['citation', 'count', 'signature'],
                      labels: const ['签名', '数量', '内部签名'],
                    ),
                    const SizedBox(height: 8),
                    SelectableText(summary.citationConsistencyPath),
                  ],
                );
              },
            ),
    );
  }

  Future<Map<String, dynamic>> _loadConsistency(String path) async {
    final text = await File(path).readAsString();
    final decoded = jsonDecode(text);
    return decoded is Map<String, dynamic> ? decoded : <String, dynamic>{};
  }
}

class JsonTableSection extends StatelessWidget {
  const JsonTableSection({
    super.key,
    required this.title,
    required this.rows,
    required this.columns,
    required this.labels,
  });

  final String title;
  final List<Map<String, dynamic>> rows;
  final List<String> columns;
  final List<String> labels;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: const BorderSide(color: Color(0xffd9ded6)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            if (rows.isEmpty)
              const Text('无')
            else
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: DataTable(
                  columns: [
                    for (final label in labels) DataColumn(label: Text(label)),
                  ],
                  rows: [
                    for (final row in rows.take(50))
                      DataRow(
                        cells: [
                          for (final col in columns)
                            DataCell(
                              ConstrainedBox(
                                constraints:
                                    const BoxConstraints(maxWidth: 280),
                                child: SelectableText(
                                  trimStr(asText(row[col]), 120),
                                ),
                              ),
                            ),
                        ],
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

List<Map<String, dynamic>> listOf(Object? value) {
  if (value is! List) return const <Map<String, dynamic>>[];
  return value
      .whereType<Map>()
      .map((item) => item.map((key, value) => MapEntry(key.toString(), value)))
      .toList();
}

String asText(Object? value) => value?.toString() ?? '';

class EntryDetailDialog extends StatelessWidget {
  const EntryDetailDialog({super.key, required this.item});

  final EntryResult item;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(item.key.isEmpty ? '条目详情' : item.key),
      content: SizedBox(
        width: 760,
        height: 620,
        child: ListView(
          children: [
            DetailSection(
              title: '数据库核验结果',
              children: [
                DetailRow(label: '原标题', value: item.title),
                DetailRow(label: '匹配标题', value: item.matchedTitle),
                DetailRow(label: '来源', value: item.source),
                DetailRow(
                  label: '标题相似度',
                  value: item.similarity == null
                      ? ''
                      : '${(item.similarity! * 100).round()}%',
                ),
                DetailRow(
                  label: '作者核查',
                  value: _joinStatus(item.authorCheck, item.authorReason),
                ),
                DetailRow(
                  label: '年份核查',
                  value: _joinStatus(item.yearCheck, item.yearReason),
                ),
                DetailRow(
                  label: 'DOI 核查',
                  value: _joinStatus(item.doiCheck, item.doiReason),
                ),
                DetailRow(label: '输入 DOI', value: item.bibDoi),
                DetailRow(label: '数据源 DOI', value: item.matchedDoi),
                DetailRow(
                  label: '候选数量',
                  value:
                      item.candidateCount > 0 ? '${item.candidateCount}' : '',
                ),
                DetailRow(label: '多来源仲裁', value: item.arbitrationReason),
                DetailRow(label: '来源核验轨迹', value: item.sourceTrace),
                DetailRow(label: '备选候选', value: item.alternativeCandidates),
                DetailRow(
                  label: '候选冲突',
                  value: item.candidateConflict == 'Yes' ? '存在冲突，需人工裁决' : '',
                ),
              ],
            ),
            DetailSection(
              title: '风险解释',
              children: [
                SelectableText(item.riskExplanation),
              ],
            ),
            DetailSection(
              title: '修复建议',
              children: [
                SelectableText(
                  _withOptionalBasis(
                    item.fixSuggestion.isNotEmpty
                        ? item.fixSuggestion
                        : item.suggestedAction,
                    item.fixSuggestionBasis,
                  ),
                ),
              ],
            ),
            DetailSection(
              title: '规范引用',
              children: [
                if (!item.standardCitationAvailable)
                  const Text('未找到可靠数据库匹配时不会生成或补造规范引用。')
                else ...[
                  if (item.standardCitationBasis.isNotEmpty)
                    SelectableText('依据：${item.standardCitationBasis}'),
                  const SizedBox(height: 8),
                  CitationBlock(label: 'APA', value: item.standardCitationApa),
                  CitationBlock(
                      label: 'BibTeX', value: item.standardCitationBibtex),
                  CitationBlock(
                      label: 'GB/T 7714', value: item.standardCitationGbt7714),
                ],
              ],
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('关闭'),
        ),
      ],
    );
  }
}

class DetailSection extends StatelessWidget {
  const DetailSection({super.key, required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: const BorderSide(color: Color(0xffd9ded6)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            ...children,
          ],
        ),
      ),
    );
  }
}

class DetailRow extends StatelessWidget {
  const DetailRow({super.key, required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    if (value.trim().isEmpty) {
      return const SizedBox.shrink();
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 92,
            child: Text(
              label,
              style: const TextStyle(color: Color(0xff596158)),
            ),
          ),
          Expanded(child: SelectableText(value)),
        ],
      ),
    );
  }
}

class CitationBlock extends StatelessWidget {
  const CitationBlock({super.key, required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    if (value.trim().isEmpty) {
      return const SizedBox.shrink();
    }
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: const Color(0xfff7f8f5),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: const Color(0xffd9ded6)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(label,
                        style: const TextStyle(fontWeight: FontWeight.w700)),
                  ),
                  TextButton.icon(
                    onPressed: () =>
                        Clipboard.setData(ClipboardData(text: value)),
                    icon: const Icon(Icons.copy_rounded, size: 16),
                    label: const Text('复制'),
                  ),
                ],
              ),
              SelectableText(value),
            ],
          ),
        ),
      ),
    );
  }
}

String _joinStatus(String status, String reason) {
  if (status.isEmpty) return reason;
  if (reason.isEmpty) return status;
  return '$status：$reason';
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

class ExplanationTile extends StatelessWidget {
  const ExplanationTile({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.body,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final String body;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: const Color(0xffd9ded6)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: const Color(0xff1f7a6d)),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  if (subtitle.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(
                      trimStr(subtitle, 120),
                      style: const TextStyle(
                        color: Color(0xff596158),
                        fontSize: 12,
                      ),
                    ),
                  ],
                  const SizedBox(height: 8),
                  SelectableText(body),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class InfoBox extends StatelessWidget {
  const InfoBox({
    super.key,
    required this.icon,
    required this.title,
    required this.text,
  });

  final IconData icon;
  final String title;
  final String text;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: const Color(0xffeef6f2),
        border: Border.all(color: const Color(0xffcfe0d7)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: const Color(0xff1f7a6d)),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 4),
                  Text(text),
                ],
              ),
            ),
          ],
        ),
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
        color: const Color(0xfffbfcfa),
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

String _withOptionalBasis(String text, String basis) {
  final cleanBasis = basis.trim();
  if (cleanBasis.isEmpty) {
    return text;
  }
  return '$text\n\n依据：$cleanBasis';
}

String _riskLabel(String level) {
  return switch (level) {
    'high' => '高风险',
    'medium' => '中风险',
    'low' => '低风险',
    _ => '无明显风险',
  };
}
