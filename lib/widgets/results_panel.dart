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
      title: '\u7ed3\u8bba\u4e0e\u5b57\u6bb5\u5bf9\u6bd4',
      child: results.isEmpty
          ? const Center(child: Text('\u6682\u65e0\u6761\u76ee'))
          : ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: results.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (context, index) {
                final item = results[index];
                return _ResultCard(
                  item: item,
                  onTap: () => _showEntryDetail(context, item),
                );
              },
            ),
    );
  }

  void _showEntryDetail(BuildContext context, EntryResult item) {
    showDialog<void>(
      context: context,
      builder: (ctx) => EntryDetailDialog(item: item),
    );
  }
}

class _ResultCard extends StatelessWidget {
  const _ResultCard({required this.item, required this.onTap});

  final EntryResult item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final source = item.adoptedSource.isEmpty ? item.source : item.adoptedSource;
    final sim = _titleSimilarityText(item);
    return Card(
      elevation: 0,
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: _statusColor(item).withValues(alpha: 0.35)),
      ),
      child: InkWell(
        onTap: onTap,
        child: IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(width: 5, color: _statusColor(item)),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(_statusIcon(item), color: _statusColor(item)),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  item.key.isEmpty ? '\u672a\u547d\u540d\u6761\u76ee' : item.key,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w800,
                                    fontSize: 15,
                                  ),
                                ),
                                const SizedBox(height: 3),
                                Text(
                                  _primaryConclusion(item),
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    color: Color(0xff3f493f),
                                    height: 1.25,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 8),
                          _InfoPill(
                            label: _riskLabel(item.riskLevel),
                            color: _riskColor(item.riskLevel),
                          ),
                          const SizedBox(width: 6),
                          _InfoPill(
                            label: '\u7f6e\u4fe1\u5ea6 ${item.confidenceScore}',
                            color: const Color(0xff1f7a6d),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        item.title.isEmpty ? item.reason : item.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          _MiniComparePill(
                            label: '\u6807\u9898',
                            status: _titleStatus(item),
                            text: sim.isEmpty
                                ? (_titleComparisonNotApplicable(item) ? '未提供' : '\u5f85\u786e\u8ba4')
                                : sim,
                          ),
                          _MiniComparePill(
                            label: '\u4f5c\u8005',
                            status: item.authorCheck,
                            text: _fieldStatusText(item.authorCheck),
                          ),
                          _MiniComparePill(
                            label: '\u5e74\u4efd',
                            status: item.yearCheck,
                            text: _fieldStatusText(item.yearCheck),
                          ),
                          _MiniComparePill(
                            label: 'DOI',
                            status: item.doiCheckStatus.isNotEmpty
                                ? item.doiCheckStatus
                                : item.doiCheck,
                            text: item.doiCheckStatus.isNotEmpty
                                ? _doiStatusLabel(item.doiCheckStatus)
                                : _fieldStatusText(item.doiCheck),
                          ),
                          if (source.isNotEmpty)
                            _InfoPill(
                              label: source + (sim.isEmpty ? '' : ' · $sim'),
                              color: const Color(0xff596158),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 8),
                child: Icon(Icons.chevron_right_rounded, color: Color(0xff8b948b)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MiniComparePill extends StatelessWidget {
  const _MiniComparePill({
    required this.label,
    required this.status,
    required this.text,
  });

  final String label;
  final String status;
  final String text;

  @override
  Widget build(BuildContext context) {
    final color = _comparisonColor(status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        border: Border.all(color: color.withValues(alpha: 0.35)),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(_comparisonIcon(status), size: 14, color: color),
          const SizedBox(width: 5),
          Text(
            '$label：$text',
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w700,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

class _InfoPill extends StatelessWidget {
  const _InfoPill({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    if (label.trim().isEmpty) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w800,
          fontSize: 12,
        ),
      ),
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

List<Map<String, dynamic>> _webEvidenceRows(EntryResult item) {
  final raw = item.webEvidenceResults.trim();
  if (raw.isEmpty) return const <Map<String, dynamic>>[];
  try {
    final decoded = jsonDecode(raw);
    if (decoded is List) {
      return decoded
          .whereType<Map>()
          .map((row) => row.map((key, value) => MapEntry(key.toString(), value)))
          .toList();
    }
  } catch (_) {
    return const <Map<String, dynamic>>[];
  }
  return const <Map<String, dynamic>>[];
}

String _webEvidenceRowText(Map<String, dynamic> row) {
  return _joinNonEmpty([
    asText(row['title']),
    asText(row['url']),
    asText(row['snippet']),
  ], sep: '\n');
}


class EntryDetailDialog extends StatelessWidget {
  const EntryDetailDialog({super.key, required this.item});

  final EntryResult item;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      titlePadding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
      title: Row(
        children: [
          Icon(_statusIcon(item), color: _statusColor(item)),
          const SizedBox(width: 8),
          Expanded(child: Text(item.key.isEmpty ? '\u6761\u76ee\u8be6\u60c5' : item.key)),
          _InfoPill(label: _riskLabel(item.riskLevel), color: _riskColor(item.riskLevel)),
        ],
      ),
      content: SizedBox(
        width: 920,
        height: 700,
        child: ListView(
          children: [
            _ConclusionCard(item: item),
            FieldComparisonSection(item: item),
            WebEvidenceSection(item: item),
            DetailSection(
              title: '\u89e3\u6790\u4e0e\u68c0\u7d22\u8def\u5f84',
              children: [
                DetailRow(label: '\u89e3\u6790\u65b9\u5f0f', value: _parserLabel(item)),
                DetailRow(label: '\u89e3\u6790\u63d0\u793a', value: item.parserWarning),
                DetailRow(
                  label: '\u641c\u7d22\u6a21\u5f0f',
                  value: item.searchMode == 'parallel' ? '\u5feb\u901f\u5e76\u53d1' : '\u4e25\u683c\u987a\u5e8f',
                ),
                DetailRow(label: '\u641c\u7d22\u94fe', value: item.sourceOrder),
                DetailRow(
                  label: '\u6700\u7ec8\u91c7\u7528',
                  value: item.adoptedSource.isEmpty ? item.source : item.adoptedSource,
                ),
                DetailRow(label: '\u5b9e\u9645\u8def\u5f84', value: item.actualQueryTrace),
                DetailRow(label: '\u591a\u6765\u6e90\u4ef2\u88c1', value: item.arbitrationReason),
                DetailRow(label: '\u6765\u6e90\u8f68\u8ff9', value: item.sourceTrace),
                DetailRow(label: '\u5907\u9009\u5019\u9009', value: item.alternativeCandidates),
                DetailRow(
                  label: '\u5019\u9009\u51b2\u7a81',
                  value: item.candidateConflict == 'Yes' ? '\u5b58\u5728\u51b2\u7a81\uff0c\u5efa\u8bae\u4eba\u5de5\u88c1\u51b3' : '',
                ),
              ],
            ),
            DetailSection(
              title: '\u89c4\u8303\u5f15\u7528',
              children: [
                if (!item.standardCitationAvailable)
                  const Text('\u672a\u627e\u5230\u53ef\u9760\u6570\u636e\u5e93\u5339\u914d\u65f6\u4e0d\u4f1a\u751f\u6210\u6216\u8865\u9020\u89c4\u8303\u5f15\u7528\u3002')
                else ...[
                  if (item.standardCitationBasis.isNotEmpty)
                    SelectableText('\u4f9d\u636e\uff1a${item.standardCitationBasis}'),
                  const SizedBox(height: 8),
                  CitationBlock(label: 'APA', value: item.standardCitationApa),
                  CitationBlock(label: 'BibTeX', value: item.standardCitationBibtex),
                  CitationBlock(label: 'GB/T 7714', value: item.standardCitationGbt7714),
                ],
              ],
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('\u5173\u95ed'),
        ),
      ],
    );
  }
}

class _ConclusionCard extends StatelessWidget {
  const _ConclusionCard({required this.item});

  final EntryResult item;

  @override
  Widget build(BuildContext context) {
    final source = item.adoptedSource.isEmpty ? item.source : item.adoptedSource;
    final sim = _titleSimilarityText(item);
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      color: _statusColor(item).withValues(alpha: 0.08),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: _statusColor(item).withValues(alpha: 0.30)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(_statusIcon(item), color: _statusColor(item)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _primaryConclusion(item),
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _InfoPill(label: '\u7f6e\u4fe1\u5ea6 ${item.confidenceScore}', color: const Color(0xff1f7a6d)),
                _InfoPill(label: source, color: const Color(0xff596158)),
                if (sim.isNotEmpty) _InfoPill(label: sim, color: const Color(0xff596158)),
                _InfoPill(label: _riskLabel(item.riskLevel), color: _riskColor(item.riskLevel)),
              ],
            ),
            if (item.riskExplanation.isNotEmpty) ...[
              const SizedBox(height: 10),
              _RiskSummaryBlock(item: item),
            ],
            if ((item.fixSuggestion.isNotEmpty || item.suggestedAction.isNotEmpty) &&
                (item.fixSuggestion.isNotEmpty ? item.fixSuggestion : item.suggestedAction) != '\u65e0\u9700\u5904\u7406\u3002') ...[
              const SizedBox(height: 10),
              DecoratedBox(
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.75),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xffd9ded6)),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(10),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.tips_and_updates_outlined, size: 18, color: Color(0xffb54708)),
                      const SizedBox(width: 8),
                      Expanded(
                        child: SelectableText(
                          item.fixSuggestion.isNotEmpty ? item.fixSuggestion : item.suggestedAction,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _RiskSummaryBlock extends StatelessWidget {
  const _RiskSummaryBlock({required this.item});

  final EntryResult item;

  @override
  Widget build(BuildContext context) {
    final color = _riskColor(item.riskLevel);
    final points = _riskSummaryPoints(item);
    final fullText = item.riskExplanation.trim();
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffd9ded6)),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(10, 10, 10, 6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.fact_check_outlined, size: 18, color: color),
                const SizedBox(width: 6),
                const Text(
                  '主要原因',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
              ],
            ),
            const SizedBox(height: 8),
            if (points.isEmpty)
              SelectableText(
                trimStr(fullText, 180),
                style: const TextStyle(height: 1.35),
              )
            else
              for (final point in points.take(4)) _BulletLine(text: point),
            if (fullText.length > 180 || points.isNotEmpty) ...[
              const SizedBox(height: 4),
              Theme(
                data: Theme.of(context)
                    .copyWith(dividerColor: Colors.transparent),
                child: Material(
                  color: Colors.transparent,
                  child: ExpansionTile(
                    tilePadding: EdgeInsets.zero,
                    childrenPadding: const EdgeInsets.only(top: 4, bottom: 4),
                    dense: true,
                    title: const Text(
                      '查看完整解释',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: Color(0xff596158),
                      ),
                    ),
                    children: [
                      Align(
                        alignment: Alignment.centerLeft,
                        child: SelectableText(
                          fullText,
                          style: const TextStyle(
                            color: Color(0xff596158),
                            fontSize: 12,
                            height: 1.35,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _BulletLine extends StatelessWidget {
  const _BulletLine({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(top: 7),
            child: Icon(Icons.circle, size: 5, color: Color(0xff596158)),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: SelectableText(
              text,
              style: const TextStyle(height: 1.35),
            ),
          ),
        ],
      ),
    );
  }
}

class FieldComparisonSection extends StatelessWidget {
  const FieldComparisonSection({super.key, required this.item});

  final EntryResult item;

  @override
  Widget build(BuildContext context) {
    final matchedUrl = item.matchedUrl.isNotEmpty ? item.matchedUrl : item.doiResolvedUrl;
    final doiHint = _joinNonEmpty([
      item.doiReason,
      item.doiCheckMessage,
    ]);
    return DetailSection(
      title: '\u5b57\u6bb5\u5bf9\u6bd4',
      children: [
        const Padding(
          padding: EdgeInsets.only(bottom: 8),
          child: Text(
            '\u5de6\u4fa7\u662f\u7a0b\u5e8f\u89e3\u6790\u51fa\u7684\u8f93\u5165\u5b57\u6bb5\uff0c\u53f3\u4fa7\u662f\u6700\u7ec8\u91c7\u7528\u7684\u6570\u636e\u6e90\u8fd4\u56de\u5b57\u6bb5\uff1b\u6bcf\u4e00\u884c\u7ed9\u51fa\u53ef\u76f4\u63a5\u5224\u65ad\u7684\u63d0\u793a\u3002',
            style: TextStyle(color: Color(0xff596158)),
          ),
        ),
        ComparisonRow(
          label: '\u6807\u9898',
          input: _titleInputValue(item),
          matched: _titleMatchedValue(item),
          status: _titleStatus(item),
          hint: _titleHint(item),
        ),
        ComparisonRow(
          label: '\u4f5c\u8005',
          input: item.bibAuthors,
          matched: item.matchedAuthors,
          status: item.authorCheck,
          hint: _authorHint(item),
        ),
        ComparisonRow(
          label: '\u5e74\u4efd',
          input: item.bibYear,
          matched: item.matchedYear,
          status: item.yearCheck,
          hint: item.yearReason,
        ),
        ComparisonRow(
          label: 'DOI',
          input: item.bibDoi,
          matched: item.matchedDoi.isEmpty ? item.doiTargetDoi : item.matchedDoi,
          status: item.doiCheckStatus.isNotEmpty ? item.doiCheckStatus : item.doiCheck,
          hint: doiHint,
        ),
        ComparisonRow(
          label: '\u7f51\u5740',
          input: item.bibUrl,
          matched: matchedUrl,
          status: _urlStatus(item, matchedUrl),
          hint: _urlHint(item, matchedUrl),
        ),
        ComparisonRow(
          label: '\u6765\u6e90/\u7c7b\u578b',
          input: '',
          matched: _joinNonEmpty([item.source, item.matchedVenue, item.matchedType], sep: ' \u00b7 '),
          status: item.status == 'found' ? 'exact' : item.status,
          hint: item.reason,
        ),
        if (item.doiTargetTitle.isNotEmpty || item.doiTargetYear.isNotEmpty)
          ComparisonRow(
            label: 'DOI \u6307\u5411',
            input: item.bibDoi,
            matched: _joinNonEmpty([item.doiTargetTitle, item.doiTargetYear, item.doiTargetDoi], sep: ' \u00b7 '),
            status: item.doiCheckStatus,
            hint: item.doiCheckMessage,
          ),
      ],
    );
  }
}

class WebEvidenceSection extends StatelessWidget {
  const WebEvidenceSection({super.key, required this.item});

  final EntryResult item;

  @override
  Widget build(BuildContext context) {
    final rows = _webEvidenceRows(item);
    final hasEvidence = item.webEvidence ||
        item.webEvidenceLinks.trim().isNotEmpty ||
        rows.isNotEmpty;
    if (!hasEvidence) {
      return const SizedBox.shrink();
    }
    final note = item.webEvidenceNote.trim().isEmpty
        ? '网页搜索源只返回候选页面，不返回结构化作者、年份、DOI 等文献元数据；请点击页面人工核对。'
        : item.webEvidenceNote.trim();
    return DetailSection(
      title: '网页搜索证据（仅辅助）',
      children: [
        InfoBox(
          icon: Icons.travel_explore_rounded,
          title: '不是元数据验证',
          text: note,
        ),
        const SizedBox(height: 10),
        if (rows.isNotEmpty)
          for (final row in rows.take(5))
            DetailRow(
              label: '#${asText(row['rank']).isEmpty ? rows.indexOf(row) + 1 : asText(row['rank'])}',
              value: _webEvidenceRowText(row),
            )
        else
          DetailRow(label: '候选页面', value: item.webEvidenceLinks),
      ],
    );
  }
}

class ComparisonRow extends StatelessWidget {
  const ComparisonRow({
    super.key,
    required this.label,
    required this.input,
    required this.matched,
    required this.status,
    required this.hint,
  });

  final String label;
  final String input;
  final String matched;
  final String status;
  final String hint;

  @override
  Widget build(BuildContext context) {
    final color = _comparisonColor(status);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: const Color(0xffd9ded6)),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 76,
              child: Text(label, style: const TextStyle(fontWeight: FontWeight.w800)),
            ),
            Expanded(child: _ComparisonValue(title: '\u89e3\u6790\u8f93\u5165', value: input)),
            const SizedBox(width: 10),
            Expanded(child: _ComparisonValue(title: '\u67e5\u8be2\u8fd4\u56de', value: matched)),
            const SizedBox(width: 10),
            SizedBox(
              width: 210,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _MiniComparePill(
                    label: '\u7ed3\u8bba',
                    status: status,
                    text: _fieldStatusText(status),
                  ),
                  if (hint.trim().isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      hint,
                      style: TextStyle(color: color, fontSize: 12, height: 1.3),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ComparisonValue extends StatelessWidget {
  const _ComparisonValue({required this.title, required this.value});

  final String title;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(color: Color(0xff596158), fontSize: 12)),
        const SizedBox(height: 3),
        LinkableSelectableText(value: value.trim().isEmpty ? '?' : value),
      ],
    );
  }
}

class LinkableSelectableText extends StatelessWidget {
  const LinkableSelectableText({super.key, required this.value});

  final String value;

  @override
  Widget build(BuildContext context) {
    final links = _extractExternalLinks(value);
    if (links.isEmpty) {
      return SelectableText(value, style: const TextStyle(height: 1.25));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SelectableText(value, style: const TextStyle(height: 1.25)),
        const SizedBox(height: 6),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: [
            for (final link in links)
              ActionChip(
                avatar: const Icon(Icons.open_in_new_rounded, size: 16),
                label: Text(link.isDoi ? '打开 DOI' : '打开链接'),
                visualDensity: VisualDensity.compact,
                onPressed: () => _openExternalLink(context, link.url),
              ),
          ],
        ),
      ],
    );
  }
}

class _ExternalLink {
  const _ExternalLink({required this.url, required this.isDoi});

  final String url;
  final bool isDoi;
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
          Expanded(child: LinkableSelectableText(value: value)),
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

List<_ExternalLink> _extractExternalLinks(String value) {
  final text = value.trim();
  if (text.isEmpty || text == '?') return const [];
  final links = <_ExternalLink>[];
  final seen = <String>{};
  final urlSpans = <({int start, int end})>[];

  final urlPattern = RegExp(
    r'https?://[^\s<>"\]）)}；;，,。]+',
    caseSensitive: false,
  );
  for (final match in urlPattern.allMatches(text)) {
    final raw = match.group(0) ?? '';
    final url = _trimLinkToken(raw);
    if (url.isEmpty) continue;
    urlSpans.add((start: match.start, end: match.end));
    if (seen.add(url.toLowerCase())) {
      links.add(_ExternalLink(
        url: url,
        isDoi: url.toLowerCase().contains('doi.org/'),
      ));
    }
  }

  final doiPattern = RegExp(
    r'10\.\d{4,9}/[-._;()/:A-Z0-9]+',
    caseSensitive: false,
  );
  for (final match in doiPattern.allMatches(text)) {
    final insideUrl =
        urlSpans.any((span) => match.start >= span.start && match.end <= span.end);
    if (insideUrl) continue;
    final doi = _trimLinkToken(match.group(0) ?? '');
    if (doi.isEmpty) continue;
    final url = 'https://doi.org/$doi';
    if (seen.add(url.toLowerCase())) {
      links.add(_ExternalLink(url: url, isDoi: true));
    }
  }

  return links;
}

String _trimLinkToken(String value) {
  var text = value.trim();
  while (text.isNotEmpty && RegExp(r'[.,;:，。；、]$').hasMatch(text)) {
    text = text.substring(0, text.length - 1);
  }
  return text;
}

Future<void> _openExternalLink(BuildContext context, String url) async {
  final messenger = ScaffoldMessenger.maybeOf(context);
  try {
    if (Platform.isWindows) {
      await Process.run('explorer', [url]);
    } else if (Platform.isMacOS) {
      await Process.run('open', [url]);
    } else {
      await Process.run('xdg-open', [url]);
    }
  } catch (error) {
    messenger?.showSnackBar(
      SnackBar(content: Text('无法打开链接：$url ($error)')),
    );
  }
}

IconData _statusIcon(EntryResult item) {
  if (_isWebEvidenceItem(item)) {
    return Icons.travel_explore_rounded;
  }
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
  if (_isWebEvidenceItem(item)) {
    return const Color(0xffb54708);
  }
  if (item.status == 'found' && !item.needsReview) {
    return const Color(0xff276b37);
  }
  if (item.status == 'found' || item.needsReview) {
    return const Color(0xffb54708);
  }
  return const Color(0xffb42318);
}

bool _isWebEvidenceItem(EntryResult item) {
  final source = (item.adoptedSource.isEmpty ? item.source : item.adoptedSource).toLowerCase();
  return item.webEvidence ||
      item.evidenceKind.toLowerCase() == 'web' ||
      source.contains('web evidence') ||
      source.startsWith('brave ');
}

Color _riskColor(String level) {
  return switch (level) {
    'high' => const Color(0xffb42318),
    'medium' => const Color(0xffb54708),
    'low' => const Color(0xff276b37),
    _ => const Color(0xff596158),
  };
}

String _titleStatus(EntryResult item) {
  if (_titleComparisonNotApplicable(item)) return 'not_provided';
  final sim = item.similarity;
  if (item.matchedTitle.isEmpty) return 'unknown';
  if (sim == null) return 'partial';
  if (sim >= 0.98) return 'exact';
  if (sim >= 0.85) return 'partial';
  return 'mismatch';
}

bool _titleComparisonNotApplicable(EntryResult item) {
  final title = item.title.trim();
  return title.isEmpty || _looksLikeLocatorOnly(title);
}

bool _looksLikeLocatorOnly(String value) {
  final text = value.trim();
  if (text.isEmpty) return false;
  return RegExp(
    r'^(?:https?://\S+|doi\s*:\s*10\.\S+|10\.\d{4,9}/\S+)$',
    caseSensitive: false,
  ).hasMatch(text);
}

String _titleSimilarityText(EntryResult item) {
  if (_titleComparisonNotApplicable(item)) return '';
  final sim = item.similarity;
  return sim == null ? '' : '标题相似度 ${(sim * 100).round()}%';
}

String _titleInputValue(EntryResult item) {
  return _titleComparisonNotApplicable(item) ? '未提供（输入为 DOI/URL）' : item.title;
}

String _titleMatchedValue(EntryResult item) {
  if (!_titleComparisonNotApplicable(item)) return item.matchedTitle;
  if (item.doiTargetTitle.isNotEmpty) return item.doiTargetTitle;
  if (item.matchedTitle.isNotEmpty && !_looksLikeLocatorOnly(item.matchedTitle)) {
    return item.matchedTitle;
  }
  return '不适用';
}

String _titleHint(EntryResult item) {
  if (_titleComparisonNotApplicable(item)) {
    final target = _titleMatchedValue(item);
    if (target != '不适用') {
      return '输入只有 DOI/URL，没有可比较的标题；右侧为 DOI/数据源解析到的题名，标题相似度不适用。';
    }
    return '输入只有 DOI/URL，没有可比较的标题；请查看 DOI/网址行确认链接是否可解析。';
  }
  return item.similarity == null
      ? '\u672a\u8fd4\u56de\u53ef\u6bd4\u8f83\u6807\u9898'
      : '\u6807\u9898\u76f8\u4f3c\u5ea6 ${(item.similarity! * 100).round()}%';
}

Color _comparisonColor(String status) {
  return switch (status) {
    'exact' || 'matched' || 'found' => const Color(0xff276b37),
    'partial' || 'missing_in_bib' || 'no_metadata' || 'unresolved' =>
      const Color(0xffb54708),
    'mismatch' || 'not_found' || 'failed' => const Color(0xffb42318),
    'not_provided' || 'unknown' => const Color(0xff596158),
    _ => const Color(0xff596158),
  };
}

IconData _comparisonIcon(String status) {
  return switch (status) {
    'exact' || 'matched' || 'found' => Icons.check_circle_outline_rounded,
    'partial' || 'missing_in_bib' || 'no_metadata' || 'unresolved' =>
      Icons.info_outline_rounded,
    'mismatch' || 'not_found' || 'failed' => Icons.error_outline_rounded,
    'not_provided' || 'unknown' => Icons.remove_circle_outline_rounded,
    _ => Icons.help_outline_rounded,
  };
}

String _fieldStatusText(String status) {
  return switch (status) {
    'exact' => '一致',
    'matched' => '通过',
    'partial' => '需抽查',
    'mismatch' => '不一致',
    'missing_in_bib' => '输入缺失',
    'unresolved' => '无法解析',
    'no_metadata' => '无元数据',
    'not_provided' => '未提供',
    'found' => '已找到',
    'not_found' => '未找到',
    'skipped' => '已跳过',
    '' => '未知',
    _ => status,
  };
}

String _primaryConclusion(EntryResult item) {
  if (item.status == 'skipped') {
    return item.reason.isEmpty ? '已跳过：缺少可核查字段' : '已跳过：${item.reason}';
  }
  if (item.status == 'not_found' || item.status.isEmpty) {
    return item.reason.isEmpty ? '未找到可靠匹配，建议人工检索确认。' : '未找到可靠匹配：${item.reason}';
  }
  if (_titleComparisonNotApplicable(item) && item.doiCheckStatus == 'matched') {
    final title = item.doiTargetTitle.isNotEmpty ? '：${item.doiTargetTitle}' : '';
    return '输入为 DOI/URL，已通过 DOI 精确核验$title。';
  }
  if (_isWebEvidenceItem(item) && item.status == 'found') {
    return '发现网页搜索证据；请点击候选页面人工核对，不能直接视为元数据验证通过。';
  }
  if (item.needsReview || item.riskLevel == 'high') {
    return item.suggestedAction.isEmpty
        ? '找到候选记录，但存在高风险差异，建议人工核查。'
        : item.suggestedAction;
  }
  if (item.riskLevel == 'medium') {
    return item.suggestedAction.isEmpty
        ? '找到候选记录，存在部分字段差异，建议抽查。'
        : item.suggestedAction;
  }
  return '未发现明显冲突，可展开查看逐字段证据。';
}

List<String> _riskSummaryPoints(EntryResult item) {
  final points = <String>[];

  void add(String value) {
    final text = value.trim();
    if (text.isNotEmpty && !points.contains(text)) {
      points.add(text);
    }
  }

  final source = item.adoptedSource.isEmpty ? item.source : item.adoptedSource;
  final sim = _titleSimilarityText(item);
  if (source.isNotEmpty) {
    add('最终采用 $source${sim.isEmpty ? '' : '，$sim'}。');
  } else if (sim.isNotEmpty) {
    add(sim);
  }

  final doiStatus =
      item.doiCheckStatus.isNotEmpty ? item.doiCheckStatus : item.doiCheck;
  final candidateDoi =
      _joinNonEmpty([item.matchedDoi, item.doiTargetDoi], sep: ' / ');
  if (doiStatus == 'missing_in_bib' ||
      (item.bibDoi.isEmpty && candidateDoi.isNotEmpty)) {
    add('输入记录缺少 DOI；数据源提供候选 DOI：$candidateDoi。');
  } else if (doiStatus == 'mismatch') {
    add('DOI 不一致：输入 ${_emptyAsDash(item.bibDoi)}，数据源 ${_emptyAsDash(candidateDoi)}。');
  } else if (doiStatus == 'unresolved') {
    add('DOI 无法解析，建议打开 DOI/出版页人工确认。');
  }

  if (item.yearCheck == 'mismatch') {
    add('年份不一致：输入 ${_emptyAsDash(item.bibYear)}，数据源 ${_emptyAsDash(item.matchedYear)}。');
  } else if (item.yearCheck == 'exact' && item.bibYear.isNotEmpty) {
    add('年份一致：${item.bibYear}。');
  }

  if (item.authorCheck == 'mismatch' || item.authorCheck == 'partial') {
    add(item.authorReason.isEmpty ? _authorHint(item) : item.authorReason);
  }

  if (points.length < 2 && item.riskExplanation.isNotEmpty) {
    for (final clause in _shortClauses(item.riskExplanation)) {
      add(clause);
      if (points.length >= 3) break;
    }
  }

  return points;
}

List<String> _shortClauses(String text) {
  final normalized = text.replaceAll(RegExp(r'\s+'), ' ').trim();
  if (normalized.isEmpty) return const [];
  return normalized
      .split(RegExp(r'[;；。]'))
      .map((part) => part.trim())
      .where((part) => part.isNotEmpty)
      .map((part) => part.length > 90 ? '${part.substring(0, 90)}…' : part)
      .toList();
}

String _emptyAsDash(String value) => value.trim().isEmpty ? '—' : value.trim();

String _authorHint(EntryResult item) {
  final parts = <String>[];
  if (item.authorReason.isNotEmpty) parts.add(item.authorReason);
  if (item.missingAuthors.isNotEmpty) {
    parts.add('输入可能缺少：${item.missingAuthors}');
  }
  if (item.extraAuthors.isNotEmpty) {
    parts.add('输入可能额外包含：${item.extraAuthors}');
  }
  if (item.bibAuthorCount > 0 || item.matchedAuthorCount > 0) {
    parts.add('输入 ${item.bibAuthorCount} 位，返回 ${item.matchedAuthorCount} 位');
  }
  return _joinNonEmpty(parts);
}

String _urlStatus(EntryResult item, String matchedUrl) {
  if (item.bibUrl.isEmpty && matchedUrl.isEmpty) return 'not_provided';
  if (item.bibUrl.isEmpty || matchedUrl.isEmpty) return 'partial';
  final left = item.bibUrl.toLowerCase();
  final right = matchedUrl.toLowerCase();
  if (left == right || left.replaceFirst('https://doi.org/', '') == right.replaceFirst('https://doi.org/', '')) {
    return 'exact';
  }
  return 'partial';
}

String _urlHint(EntryResult item, String matchedUrl) {
  if (item.bibUrl.isEmpty && matchedUrl.isEmpty) {
    return '输入和数据源均未提供 URL。';
  }
  if (item.bibUrl.isEmpty) {
    return '输入未提供 URL；右侧是数据源/DOI 解析地址。';
  }
  if (matchedUrl.isEmpty) {
    return '输入提供了 URL，但数据源未返回可对比链接。';
  }
  return 'URL 可作为人工打开核对的证据；不同来源链接不一定完全相同。';
}

String _joinNonEmpty(Iterable<String> values, {String sep = '；'}) {
  return values.map((v) => v.trim()).where((v) => v.isNotEmpty).join(sep);
}

String _doiStatusLabel(String status) {
  return switch (status) {
    'matched' => '通过',
    'mismatch' => '不匹配',
    'unresolved' => '无法解析',
    'no_metadata' => '无元数据',
    'not_provided' => '未提供',
    _ => status,
  };
}

String _parserLabel(EntryResult item) {
  final parser = switch (item.parser) {
    'llm' => '大模型辅助解析',
    'bibtex' => 'BibTeX 结构化字段',
    'rules' => '本地规则解析',
    _ => item.parser.isEmpty ? '本地规则解析' : item.parser,
  };
  final mode = switch (item.llmParseMode) {
    'auto' => 'LLM 优先',
    'always' => 'LLM 优先',
    _ => '规则解析',
  };
  final confidence =
      item.parserConfidence.isEmpty ? '' : '，置信度 ${item.parserConfidence}';
  final note = item.parserNote.isEmpty ? '' : '；${item.parserNote}';
  return '$parser（$mode$confidence）$note';
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
