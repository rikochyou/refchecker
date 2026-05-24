import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;

import '../models.dart';

class CustomApiSourceEntry {
  CustomApiSourceEntry({
    required this.id,
    required this.nameController,
    required this.keyController,
    required this.envVarController,
    required this.endpointController,
    required this.methodController,
    required this.authTypeController,
    required this.apiKeyParamController,
    required this.apiKeyHeaderController,
    required this.queryParamsController,
    required this.headersController,
    required this.restProfileJsonController,
    required this.resultsPathController,
    required this.titlePathController,
    required this.authorsPathController,
    required this.yearPathController,
    required this.doiPathController,
    required this.urlPathController,
    required this.venuePathController,
    required this.typePathController,
    this.enabled = true,
    this.searchEnabled = true,
  });

  final String id;
  final TextEditingController nameController;
  final TextEditingController keyController;
  final TextEditingController envVarController;
  final TextEditingController endpointController;
  final TextEditingController methodController;
  final TextEditingController authTypeController;
  final TextEditingController apiKeyParamController;
  final TextEditingController apiKeyHeaderController;
  final TextEditingController queryParamsController;
  final TextEditingController headersController;
  final TextEditingController restProfileJsonController;
  final TextEditingController resultsPathController;
  final TextEditingController titlePathController;
  final TextEditingController authorsPathController;
  final TextEditingController yearPathController;
  final TextEditingController doiPathController;
  final TextEditingController urlPathController;
  final TextEditingController venuePathController;
  final TextEditingController typePathController;
  bool enabled;
  bool searchEnabled;

  bool get isCustomRest =>
      restProfileJsonController.text.trim().isNotEmpty ||
      endpointController.text.trim().isNotEmpty;

  CustomApiSource toSource() => CustomApiSource(
        id: id,
        name: nameController.text.trim(),
        apiKey: keyController.text.trim(),
        envVar: envVarController.text.trim(),
        enabled: enabled,
        searchEnabled: searchEnabled,
        endpoint: endpointController.text.trim(),
        method: methodController.text.trim().isEmpty
            ? 'GET'
            : methodController.text.trim().toUpperCase(),
        authType: authTypeController.text.trim().isEmpty
            ? 'none'
            : authTypeController.text.trim().toLowerCase(),
        apiKeyParam: apiKeyParamController.text.trim(),
        apiKeyHeader: apiKeyHeaderController.text.trim(),
        queryParams: queryParamsController.text.trim(),
        headers: headersController.text.trim(),
        restProfileJson: restProfileJsonController.text.trim(),
        resultsPath: resultsPathController.text.trim(),
        titlePath: titlePathController.text.trim(),
        authorsPath: authorsPathController.text.trim(),
        yearPath: yearPathController.text.trim(),
        doiPath: doiPathController.text.trim(),
        urlPath: urlPathController.text.trim(),
        venuePath: venuePathController.text.trim(),
        typePath: typePathController.text.trim(),
      );

  void dispose() {
    nameController.dispose();
    keyController.dispose();
    envVarController.dispose();
    endpointController.dispose();
    methodController.dispose();
    authTypeController.dispose();
    apiKeyParamController.dispose();
    apiKeyHeaderController.dispose();
    queryParamsController.dispose();
    headersController.dispose();
    restProfileJsonController.dispose();
    resultsPathController.dispose();
    titlePathController.dispose();
    authorsPathController.dispose();
    yearPathController.dispose();
    doiPathController.dispose();
    urlPathController.dispose();
    venuePathController.dispose();
    typePathController.dispose();
  }
}

class ControlPanel extends StatelessWidget {
  const ControlPanel({
    super.key,
    required this.bibPath,
    required this.outputDir,
    required this.activeOutputDir,
    required this.runState,
    required this.testingApiKeys,
    required this.apiKeyTestRevision,
    required this.advancedOpen,
    required this.threshold,
    required this.delay,
    required this.emailController,
    required this.sourceOrder,
    required this.sourceEnabled,
    required this.sourceNames,
    required this.onToggleSource,
    required this.onReorderSources,
    required this.customApiSources,
    required this.useTextMode,
    required this.textController,
    required this.onPickBib,
    required this.onPickOutputDir,
    required this.onTestCustomApiSource,
    required this.isTestingCustomApiSource,
    required this.apiKeyTestResultForCustomApiSource,
    required this.onAdvancedChanged,
    required this.onThresholdChanged,
    required this.onDelayChanged,
    required this.onTextModeChanged,
    required this.onSelectAllSources,
    required this.onDeselectAllSources,
    required this.onAddCustomApiSource,
    required this.onRemoveCustomApiSource,
    required this.onToggleCustomApiSourceEnabled,
  });

  final String? bibPath;
  final String? outputDir;
  final String? activeOutputDir;
  final RunState runState;
  final bool testingApiKeys;
  final ValueListenable<int> apiKeyTestRevision;
  final bool advancedOpen;
  final double threshold;
  final double delay;
  final TextEditingController emailController;
  final List<String> sourceOrder;
  final bool Function(String) sourceEnabled;
  final Map<String, String> sourceNames;
  final void Function(String, bool) onToggleSource;
  final void Function(int, int) onReorderSources;
  final List<CustomApiSourceEntry> customApiSources;
  final bool useTextMode;
  final TextEditingController textController;
  final VoidCallback onPickBib;
  final VoidCallback onPickOutputDir;
  final ValueChanged<int> onTestCustomApiSource;
  final bool Function(int) isTestingCustomApiSource;
  final ApiKeyTestResult? Function(int) apiKeyTestResultForCustomApiSource;
  final ValueChanged<bool> onAdvancedChanged;
  final ValueChanged<double> onThresholdChanged;
  final ValueChanged<double> onDelayChanged;
  final ValueChanged<bool> onTextModeChanged;
  final VoidCallback onSelectAllSources;
  final VoidCallback onDeselectAllSources;
  final VoidCallback onAddCustomApiSource;
  final ValueChanged<int> onRemoveCustomApiSource;
  final void Function(int, bool) onToggleCustomApiSourceEnabled;

  @override
  Widget build(BuildContext context) {
    final disabled = runState == RunState.running || testingApiKeys;
    return Card(
      margin: EdgeInsets.zero,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: const BorderSide(color: Color(0xffd9ded6)),
      ),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '输入',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            SegmentedButton<bool>(
              segments: const [
                ButtonSegment(
                    value: false,
                    label: Text('文件'),
                    icon: Icon(Icons.upload_file_outlined)),
                ButtonSegment(
                    value: true,
                    label: Text('粘贴文本'),
                    icon: Icon(Icons.paste_rounded)),
              ],
              selected: {useTextMode},
              onSelectionChanged: disabled
                  ? null
                  : (selected) => onTextModeChanged(selected.first),
            ),
            const SizedBox(height: 12),
            if (useTextMode) ...[
              TextField(
                controller: textController,
                enabled: !disabled,
                maxLines: 8,
                minLines: 4,
                decoration: const InputDecoration(
                  prefixIcon: Padding(
                    padding: EdgeInsets.only(bottom: 96),
                    child: Icon(Icons.text_snippet_outlined),
                  ),
                  hintText:
                      '在此粘贴参考文献文本（APA 格式）\n\n多条文献用空行分隔，例如：\n\nSmith, J. (2020). A Test Paper. Journal, 10(2). https://doi.org/10.1234/x\n\nBrown, A. (2021). Another Paper. Journal, 5(1), 10-20.',
                  helperText: '支持 APA / MLA / 任意包含 (年份) 和标题的引用文本',
                ),
              ),
            ] else ...[
              PathTile(
                icon: Icons.upload_file_outlined,
                title: '文献文件 (.bib / .docx / .txt)',
                path: bibPath,
                buttonLabel: '选择',
                onPressed: disabled ? null : onPickBib,
              ),
            ],
            const SizedBox(height: 12),
            PathTile(
              icon: Icons.folder_outlined,
              title: '结果保存位置',
              path: outputDir,
              buttonLabel: '选择',
              onPressed: disabled ? null : onPickOutputDir,
            ),
            if (activeOutputDir != null) ...[
              const SizedBox(height: 12),
              InfoLine(label: '本次输出', value: activeOutputDir!),
            ],
            const SizedBox(height: 16),
            SwitchListTile(
              value: advancedOpen,
              onChanged: disabled ? null : onAdvancedChanged,
              contentPadding: EdgeInsets.zero,
              title: const Text('高级设置'),
              secondary: const Icon(Icons.tune_rounded),
            ),
            if (advancedOpen) ...[
              const SizedBox(height: 8),
              SliderField(
                label: '标题相似度阈值',
                value: threshold,
                min: 0.60,
                max: 0.98,
                divisions: 38,
                suffix: '${(threshold * 100).round()}%',
                onChanged: disabled ? null : onThresholdChanged,
              ),
              const SizedBox(height: 8),
              SliderField(
                label: '请求间隔',
                value: clampDelaySeconds(delay),
                min: safeMinDelaySeconds,
                max: maxDelaySeconds,
                divisions:
                    ((maxDelaySeconds - safeMinDelaySeconds) / 0.05).round(),
                suffix: '${clampDelaySeconds(delay).toStringAsFixed(2)}s',
                onChanged: disabled ? null : onDelayChanged,
              ),
              const Text(
                '最低间隔已锁定为 0.50s，防止请求过快触发限流或封禁。',
                style: TextStyle(
                  color: Color(0xff596158),
                  fontSize: 11,
                  height: 1.35,
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: emailController,
                enabled: !disabled,
                decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.alternate_email_rounded),
                  labelText: '邮箱',
                  hintText: 'you@example.com',
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  const Icon(Icons.dns_outlined,
                      size: 18, color: Color(0xff596158)),
                  const SizedBox(width: 6),
                  const Expanded(
                    child: Text('数据源搜索链',
                        style: TextStyle(fontWeight: FontWeight.w700)),
                  ),
                  _MiniButton(
                    label: '全选',
                    onPressed: disabled ? null : onSelectAllSources,
                  ),
                  const SizedBox(width: 6),
                  _MiniButton(
                    label: '全不选',
                    onPressed: disabled ? null : onDeselectAllSources,
                  ),
                ],
              ),
              const SizedBox(height: 6),
              const Text(
                '拖拽排序设置搜索优先级，开关控制数据源启用/禁用',
                style: TextStyle(
                    color: Color(0xff596158), fontSize: 11, height: 1.35),
              ),
              const SizedBox(height: 6),
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    border: Border.all(color: const Color(0xffd9ded6)),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: ReorderableListView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    buildDefaultDragHandles: false,
                    itemCount: sourceOrder.length,
                    onReorderItem: disabled
                        ? (int oldIndex, int newIndex) {}
                        : onReorderSources,
                    proxyDecorator: (child, index, animation) {
                      return AnimatedBuilder(
                        animation: animation,
                        builder: (context, child) => Material(
                          elevation: 2,
                          borderRadius: BorderRadius.circular(8),
                          child: child,
                        ),
                        child: child,
                      );
                    },
                    itemBuilder: (context, index) {
                      final key = sourceOrder[index];
                      final name = sourceNames[key] ?? key;
                      final enabled = sourceEnabled(key);
                      final isAlwaysOn = key == 'crossref';
                      return Container(
                        key: ValueKey(key),
                        color: Colors.white,
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        child: Row(
                          children: [
                            ReorderableDragStartListener(
                              index: index,
                              enabled: !disabled,
                              child: const Padding(
                                padding: EdgeInsets.all(6),
                                child: Icon(Icons.drag_handle_rounded,
                                    size: 20, color: Color(0xffb0b8b0)),
                              ),
                            ),
                            Expanded(
                              child: Text(
                                name,
                                style: TextStyle(
                                  fontSize: 14,
                                  fontWeight: isAlwaysOn
                                      ? FontWeight.w700
                                      : FontWeight.w400,
                                  color:
                                      enabled ? null : const Color(0xffb0b8b0),
                                ),
                              ),
                            ),
                            if (isAlwaysOn)
                              const Padding(
                                padding: EdgeInsets.only(right: 4),
                                child: Text('始终启用',
                                    style: TextStyle(
                                        fontSize: 11,
                                        color: Color(0xff8d948b))),
                              )
                            else
                              SizedBox(
                                height: 32,
                                child: Switch(
                                  value: enabled,
                                  onChanged: disabled
                                      ? null
                                      : (value) => onToggleSource(key, value),
                                ),
                              ),
                          ],
                        ),
                      );
                    },
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  const Icon(Icons.vpn_key_outlined,
                      size: 18, color: Color(0xff596158)),
                  const SizedBox(width: 6),
                  const Expanded(
                    child: Text('API 密钥配置',
                        style: TextStyle(fontWeight: FontWeight.w700)),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: disabled
                    ? null
                    : () => _showApiKeyDialog(
                          context,
                          customApiSources,
                          runState == RunState.running,
                          apiKeyTestRevision,
                          onAddCustomApiSource,
                          onRemoveCustomApiSource,
                          onToggleCustomApiSourceEnabled,
                          onTestCustomApiSource,
                          isTestingCustomApiSource,
                          apiKeyTestResultForCustomApiSource,
                        ),
                icon: const Icon(Icons.settings_rounded, size: 18),
                label: Text('配置 API 密钥 (${customApiSources.length})'),
              ),
            ],
            const SizedBox(height: 16),
            const Divider(),
            const SizedBox(height: 8),
            const Text(
              '会自动在保存位置下创建 refchecker_时间戳 文件夹，并生成 report.md 与 result.csv。',
              style: TextStyle(color: Color(0xff596158), height: 1.35),
            ),
          ],
        ),
      ),
    );
  }
}

class _MiniButton extends StatelessWidget {
  const _MiniButton({required this.label, this.onPressed});

  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final textStyle = Theme.of(context).textTheme.labelMedium;
    return SizedBox(
      height: 28,
      child: OutlinedButton(
        style: OutlinedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 8),
          minimumSize: Size.zero,
        ),
        onPressed: onPressed,
        child: Text(label, style: textStyle),
      ),
    );
  }
}

const _restProfileJsonExample = '''{
  "endpoint": "https://api.example.com/search",
  "method": "GET",
  "authType": "bearer",
  "queryParams": {
    "q": "{title}",
    "year": "{year}"
  },
  "headers": {
    "Accept": "application/json"
  },
  "resultsPath": "results",
  "titlePath": "title",
  "authorsPath": "authors",
  "yearPath": "year",
  "doiPath": "doi",
  "urlPath": "url",
  "venuePath": "venue",
  "typePath": "type"
}''';

void _fillRestProfileExample(
  BuildContext context,
  CustomApiSourceEntry entry,
) {
  if (entry.restProfileJsonController.text.trim().isEmpty) {
    entry.restProfileJsonController.text = _restProfileJsonExample;
    return;
  }
  ScaffoldMessenger.of(context).showSnackBar(
    const SnackBar(content: Text('当前 JSON 不为空；如需示例请先清空编辑框。')),
  );
}

void _formatRestProfileJson(
  BuildContext context,
  CustomApiSourceEntry entry,
) {
  final raw = entry.restProfileJsonController.text.trim();
  if (raw.isEmpty) {
    entry.restProfileJsonController.text = _restProfileJsonExample;
    return;
  }
  try {
    final decoded = jsonDecode(raw);
    entry.restProfileJsonController.text =
        const JsonEncoder.withIndent('  ').convert(decoded);
  } catch (error) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('JSON 格式有误：$error')),
    );
  }
}

String _restProfileEndpointPreview(CustomApiSourceEntry entry) {
  final legacyEndpoint = entry.endpointController.text.trim();
  if (legacyEndpoint.isNotEmpty) {
    return legacyEndpoint;
  }
  final raw = entry.restProfileJsonController.text.trim();
  if (raw.isEmpty) {
    return '未设置 REST Profile';
  }
  try {
    final decoded = jsonDecode(raw);
    final endpoint = _endpointFromDecodedProfile(decoded);
    if (endpoint != null && endpoint.trim().isNotEmpty) {
      return endpoint.trim();
    }
    return 'JSON Profile 已填写，缺少 endpoint';
  } catch (_) {
    return 'JSON Profile 格式待检查';
  }
}

String? _endpointFromDecodedProfile(Object? decoded) {
  if (decoded is Map) {
    final endpoint = decoded['endpoint'];
    return endpoint?.toString();
  }
  if (decoded is List && decoded.isNotEmpty) {
    return _endpointFromDecodedProfile(decoded.first);
  }
  return null;
}

Future<void> _showApiKeyDialog(
  BuildContext context,
  List<CustomApiSourceEntry> sources,
  bool disabled,
  ValueListenable<int> apiKeyTestRevision,
  VoidCallback onAdd,
  ValueChanged<int> onRemove,
  void Function(int, bool) onToggleEnabled,
  ValueChanged<int> onTestSource,
  bool Function(int) isTestingSource,
  ApiKeyTestResult? Function(int) testResultForSource,
) {
  return showDialog<void>(
    context: context,
    builder: (ctx) => _ApiKeyDialog(
      sources: sources,
      disabled: disabled,
      apiKeyTestRevision: apiKeyTestRevision,
      onAdd: onAdd,
      onRemove: onRemove,
      onToggleEnabled: onToggleEnabled,
      onTestSource: onTestSource,
      isTestingSource: isTestingSource,
      testResultForSource: testResultForSource,
    ),
  );
}

class _ApiKeyDialog extends StatefulWidget {
  const _ApiKeyDialog({
    required this.sources,
    required this.disabled,
    required this.apiKeyTestRevision,
    required this.onAdd,
    required this.onRemove,
    required this.onToggleEnabled,
    required this.onTestSource,
    required this.isTestingSource,
    required this.testResultForSource,
  });

  final List<CustomApiSourceEntry> sources;
  final bool disabled;
  final ValueListenable<int> apiKeyTestRevision;
  final VoidCallback onAdd;
  final ValueChanged<int> onRemove;
  final void Function(int, bool) onToggleEnabled;
  final ValueChanged<int> onTestSource;
  final bool Function(int) isTestingSource;
  final ApiKeyTestResult? Function(int) testResultForSource;

  @override
  State<_ApiKeyDialog> createState() => _ApiKeyDialogState();
}

class _ApiKeyDialogState extends State<_ApiKeyDialog> {
  int? _expandedIndex;

  void _addSource() {
    if (widget.disabled) return;
    widget.onAdd();
    setState(() {
      _expandedIndex =
          widget.sources.isEmpty ? null : widget.sources.length - 1;
    });
  }

  void _removeSource(int index) {
    if (widget.disabled) return;
    widget.onRemove(index);
    setState(() {
      if (_expandedIndex == index) {
        _expandedIndex = null;
      } else if (_expandedIndex != null && _expandedIndex! > index) {
        _expandedIndex = _expandedIndex! - 1;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    final width = (size.width - 48).clamp(420.0, 760.0).toDouble();
    final height = (size.height - 64).clamp(460.0, 720.0).toDouble();
    final expandedIndex = _expandedIndex != null &&
            _expandedIndex! >= 0 &&
            _expandedIndex! < widget.sources.length
        ? _expandedIndex
        : null;

    return Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
      elevation: 0,
      backgroundColor: const Color(0xffeef6f2),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
      child: SizedBox(
        width: width,
        height: height,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(28, 24, 28, 20),
          child: Column(
            children: [
              Row(
                children: [
                  const Icon(Icons.vpn_key_outlined,
                      size: 24, color: Color(0xff24302a)),
                  const SizedBox(width: 10),
                  const Expanded(
                    child: Text(
                      'API 密钥配置',
                      style: TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.w700,
                        color: Color(0xff202823),
                      ),
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: widget.disabled ? null : _addSource,
                    icon: const Icon(Icons.add_rounded, size: 18),
                    label: const Text('添加'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xff1f7a6d),
                      side: const BorderSide(color: Color(0xff7d8a83)),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(18),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  '以卡片形式管理增强数据源。点击编辑展开配置；API Key 会被隐藏显示，日志中不会输出明文。',
                  style: TextStyle(
                    color: Color(0xff596158),
                    fontSize: 12,
                    height: 1.35,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Expanded(
                child: widget.sources.isEmpty
                    ? _EmptyApiKeyState(
                        onAdd: widget.disabled ? null : _addSource)
                    : ListView.separated(
                        padding: const EdgeInsets.only(bottom: 8),
                        itemCount: widget.sources.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 12),
                        itemBuilder: (context, index) {
                          return _ApiKeySourceCard(
                            entry: widget.sources[index],
                            index: index,
                            expanded: expandedIndex == index,
                            disabled: widget.disabled,
                            apiKeyTestRevision: widget.apiKeyTestRevision,
                            isTestingSource: widget.isTestingSource,
                            testResultForSource: widget.testResultForSource,
                            onEnabledChanged: (value) {
                              widget.onToggleEnabled(index, value);
                              setState(() {});
                            },
                            onTest: () => widget.onTestSource(index),
                            onToggleExpanded: () {
                              setState(() {
                                _expandedIndex =
                                    expandedIndex == index ? null : index;
                              });
                            },
                            onRemove: () => _removeSource(index),
                          );
                        },
                      ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  const Expanded(
                    child: Text(
                      '提示：Springer / IEEE / CORE 只有在填写对应 Key 且数据源开关启用时才会调用。',
                      style: TextStyle(color: Color(0xff596158), fontSize: 12),
                    ),
                  ),
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text(
                      '完成',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _EmptyApiKeyState extends StatelessWidget {
  const _EmptyApiKeyState({required this.onAdd});

  final VoidCallback? onAdd;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xffd9ded6)),
      ),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.key_off_rounded,
                size: 40, color: Color(0xff8d948b)),
            const SizedBox(height: 10),
            const Text(
              '暂无 API 密钥配置',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            const Text(
              '点击“添加”创建一个新的增强数据源。',
              style: TextStyle(color: Color(0xff596158)),
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: onAdd,
              icon: const Icon(Icons.add_rounded),
              label: const Text('添加配置'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ApiKeySourceCard extends StatelessWidget {
  const _ApiKeySourceCard({
    required this.entry,
    required this.index,
    required this.expanded,
    required this.disabled,
    required this.apiKeyTestRevision,
    required this.isTestingSource,
    required this.testResultForSource,
    required this.onEnabledChanged,
    required this.onTest,
    required this.onToggleExpanded,
    required this.onRemove,
  });

  final CustomApiSourceEntry entry;
  final int index;
  final bool expanded;
  final bool disabled;
  final ValueListenable<int> apiKeyTestRevision;
  final bool Function(int) isTestingSource;
  final ApiKeyTestResult? Function(int) testResultForSource;
  final ValueChanged<bool> onEnabledChanged;
  final VoidCallback onTest;
  final VoidCallback onToggleExpanded;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: Listenable.merge([
        entry.nameController,
        entry.keyController,
        entry.envVarController,
        entry.endpointController,
        entry.restProfileJsonController,
        apiKeyTestRevision,
      ]),
      builder: (context, _) {
        final name = entry.nameController.text.trim();
        final envVar = entry.envVarController.text.trim();
        final hasKey = entry.keyController.text.trim().isNotEmpty;
        final sourceEnabled = entry.enabled;
        final isCustomRest = entry.isCustomRest;
        final testing = isTestingSource(index);
        final testingAny = isTestingSource(-1);
        final testResult = testResultForSource(index);
        final displayName = name.isEmpty ? '未命名来源' : name;
        final detail = isCustomRest
            ? _restProfileEndpointPreview(entry)
            : (envVar.isEmpty ? '未设置环境变量名' : envVar);
        final accent = _sourceAccent(displayName, index);

        return AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          curve: Curves.easeOut,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(22),
            border: Border.all(
              color: expanded
                  ? const Color(0xff3f7cff)
                  : sourceEnabled
                      ? const Color(0xffd9ded6)
                      : const Color(0xffe2e6df),
              width: expanded ? 1.4 : 1,
            ),
            boxShadow: [
              if (expanded)
                BoxShadow(
                  color: const Color(0xff3f7cff).withValues(alpha: 0.08),
                  blurRadius: 18,
                  offset: const Offset(0, 8),
                ),
            ],
          ),
          child: Column(
            children: [
              Row(
                children: [
                  const Icon(Icons.drag_indicator_rounded,
                      size: 22, color: Color(0xffb0b8b0)),
                  const SizedBox(width: 10),
                  _SourceAvatar(
                    label: _sourceInitials(displayName),
                    color: accent,
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Flexible(
                              child: Text(
                                displayName,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w800,
                                  color: sourceEnabled
                                      ? Color(0xff202823)
                                      : Color(0xff8d948b),
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            _StatusPill(
                              label: hasKey ? '已配置 Key' : '未配置 Key',
                              color: hasKey
                                  ? const Color(0xff1f7a6d)
                                  : const Color(0xff8d948b),
                              background: hasKey
                                  ? const Color(0xffdff3ed)
                                  : const Color(0xffeef0ed),
                            ),
                            const SizedBox(width: 6),
                            _StatusPill(
                              label: sourceEnabled ? '已启用' : '未启用',
                              color: sourceEnabled
                                  ? const Color(0xff1f7a6d)
                                  : const Color(0xff8d948b),
                              background: sourceEnabled
                                  ? const Color(0xffe4f5f1)
                                  : const Color(0xffeef0ed),
                            ),
                            if (isCustomRest) ...[
                              const SizedBox(width: 6),
                              const _StatusPill(
                                label: 'REST Profile',
                                color: Color(0xff3563d8),
                                background: Color(0xffe9eefc),
                              ),
                            ],
                          ],
                        ),
                        const SizedBox(height: 5),
                        Text(
                          detail,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: detail.startsWith('未设置')
                                ? const Color(0xff8d948b)
                                : const Color(0xff3f7cff),
                            fontSize: 14,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 10),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        '启用',
                        style:
                            TextStyle(fontSize: 12, color: Color(0xff596158)),
                      ),
                      Transform.scale(
                        scale: 0.82,
                        child: Switch(
                          value: sourceEnabled,
                          onChanged: disabled ? null : onEnabledChanged,
                        ),
                      ),
                    ],
                  ),
                  IconButton(
                    tooltip: expanded ? '收起编辑' : '编辑配置',
                    onPressed: disabled ? null : onToggleExpanded,
                    icon: Icon(
                      expanded
                          ? Icons.keyboard_arrow_up_rounded
                          : Icons.edit_outlined,
                    ),
                  ),
                  IconButton(
                    tooltip: '删除配置',
                    onPressed: disabled ? null : onRemove,
                    icon: const Icon(Icons.delete_outline_rounded),
                  ),
                ],
              ),
              ClipRect(
                child: AnimatedSize(
                  duration: const Duration(milliseconds: 180),
                  curve: Curves.easeOut,
                  alignment: Alignment.topCenter,
                  child: expanded
                      ? Padding(
                          padding: const EdgeInsets.only(top: 14),
                          child: Column(
                            children: [
                              const Divider(height: 1),
                              const SizedBox(height: 14),
                              TextField(
                                controller: entry.nameController,
                                enabled: !disabled,
                                decoration: const InputDecoration(
                                  labelText: '名称 / 来源',
                                  hintText: '例如：Springer Nature',
                                  prefixIcon: Icon(Icons.dataset_outlined),
                                  isDense: true,
                                  filled: true,
                                  fillColor: Color(0xfffbfcfa),
                                ),
                              ),
                              const SizedBox(height: 10),
                              TextField(
                                controller: entry.keyController,
                                enabled: !disabled,
                                obscureText: true,
                                decoration: const InputDecoration(
                                  labelText: 'API Key',
                                  hintText: '在此粘贴密钥',
                                  prefixIcon: Icon(Icons.key_rounded),
                                  isDense: true,
                                  filled: true,
                                  fillColor: Color(0xfffbfcfa),
                                ),
                              ),
                              const SizedBox(height: 10),
                              TextField(
                                controller: entry.envVarController,
                                enabled: !disabled,
                                decoration: const InputDecoration(
                                  labelText: '环境变量名',
                                  hintText: '例如：REFCHECKER_SPRINGER_API_KEY',
                                  prefixIcon: Icon(Icons.terminal_rounded),
                                  helperText: '传递给后端进程的环境变量名称',
                                  helperMaxLines: 1,
                                  isDense: true,
                                  filled: true,
                                  fillColor: Color(0xfffbfcfa),
                                ),
                              ),
                              const SizedBox(height: 10),
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.center,
                                children: [
                                  const Expanded(
                                    child: Text(
                                      '连通性测试只使用通用关键词，不会在日志中输出 Key 明文。',
                                      style: TextStyle(
                                        color: Color(0xff596158),
                                        fontSize: 12,
                                        height: 1.35,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  OutlinedButton.icon(
                                    onPressed:
                                        disabled || testingAny ? null : onTest,
                                    icon: testing
                                        ? const SizedBox(
                                            width: 16,
                                            height: 16,
                                            child: CircularProgressIndicator(
                                                strokeWidth: 2),
                                          )
                                        : const Icon(
                                            Icons.network_check_rounded,
                                            size: 18,
                                          ),
                                    label: Text(testing ? '测试中' : '测试连接'),
                                  ),
                                ],
                              ),
                              if (testResult != null) ...[
                                const SizedBox(height: 10),
                                DecoratedBox(
                                  decoration: BoxDecoration(
                                    color: const Color(0xfffbfcfa),
                                    borderRadius: BorderRadius.circular(10),
                                    border: Border.all(
                                        color: const Color(0xffd9ded6)),
                                  ),
                                  child:
                                      ApiKeyTestResultTile(result: testResult),
                                ),
                              ],
                              const SizedBox(height: 10),
                              ExpansionTile(
                                tilePadding: EdgeInsets.zero,
                                childrenPadding:
                                    const EdgeInsets.only(top: 8, bottom: 4),
                                title: const Text(
                                  '自定义 REST API Profile（JSON，高级）',
                                  style: TextStyle(fontWeight: FontWeight.w700),
                                ),
                                subtitle: const Text(
                                  '直接粘贴一个 JSON object；填写 endpoint 后会作为自定义数据源加入搜索链。',
                                  style: TextStyle(fontSize: 12),
                                ),
                                children: [
                                  Row(
                                    children: [
                                      Expanded(
                                        child: Text(
                                          '支持模板变量：{title} / {author} / {year} / {email}。每张卡片建议只配置一个 Profile；旧版分字段配置仍会兼容读取。',
                                          style: Theme.of(context)
                                              .textTheme
                                              .bodySmall
                                              ?.copyWith(
                                                color: const Color(0xff596158),
                                                height: 1.35,
                                              ),
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      TextButton.icon(
                                        onPressed: disabled
                                            ? null
                                            : () => _fillRestProfileExample(
                                                  context,
                                                  entry,
                                                ),
                                        icon: const Icon(Icons.content_paste_go,
                                            size: 16),
                                        label: const Text('填入示例'),
                                      ),
                                      TextButton.icon(
                                        onPressed: disabled
                                            ? null
                                            : () => _formatRestProfileJson(
                                                  context,
                                                  entry,
                                                ),
                                        icon: const Icon(Icons.data_object,
                                            size: 16),
                                        label: const Text('格式化'),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 10),
                                  TextField(
                                    controller: entry.restProfileJsonController,
                                    enabled: !disabled,
                                    minLines: 12,
                                    maxLines: 18,
                                    style: const TextStyle(
                                      fontFamily: 'Consolas',
                                      fontFamilyFallback: [
                                        'Cascadia Mono',
                                        'Courier New',
                                        'monospace',
                                      ],
                                      fontSize: 12.5,
                                      height: 1.35,
                                    ),
                                    decoration: const InputDecoration(
                                      labelText: 'REST API Profile JSON',
                                      alignLabelWithHint: true,
                                      hintText: _restProfileJsonExample,
                                      helperText:
                                          'endpoint / auth / 参数模板 / JSON 字段映射都在这里配置；apiKey 可留空并使用上方 API Key。',
                                      helperMaxLines: 3,
                                      isDense: true,
                                      filled: true,
                                      fillColor: Color(0xfffbfcfa),
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        )
                      : const SizedBox.shrink(),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _SourceAvatar extends StatelessWidget {
  const _SourceAvatar({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 48,
      height: 48,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: color.withValues(alpha: 0.22)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w800,
          fontSize: 15,
        ),
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({
    required this.label,
    required this.color,
    required this.background,
  });

  final String label;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(9),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

String _sourceInitials(String name) {
  final trimmed = name.trim();
  if (trimmed.isEmpty) return '?';
  final parts =
      trimmed.split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
  if (parts.length == 1) {
    final first = parts.first;
    final end = first.length < 2 ? first.length : 2;
    return first.substring(0, end).toUpperCase();
  }
  return '${parts[0].substring(0, 1)}${parts[1].substring(0, 1)}'.toUpperCase();
}

Color _sourceAccent(String name, int index) {
  final lower = name.toLowerCase();
  if (lower.contains('springer')) return const Color(0xff00806c);
  if (lower.contains('ieee')) return const Color(0xff3563d8);
  if (lower.contains('core')) return const Color(0xffb15f00);
  const palette = [
    Color(0xff1f7a6d),
    Color(0xff3f7cff),
    Color(0xff8a5cf6),
    Color(0xffd45b7a),
    Color(0xff6b7280),
  ];
  return palette[index % palette.length];
}

class PathTile extends StatelessWidget {
  const PathTile({
    super.key,
    required this.icon,
    required this.title,
    required this.path,
    required this.buttonLabel,
    required this.onPressed,
  });

  final IconData icon;
  final String title;
  final String? path;
  final String buttonLabel;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffd9ded6)),
        color: Colors.white,
      ),
      child: Row(
        children: [
          Icon(icon),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 3),
                Text(
                  path == null ? '未选择' : p.normalize(path!),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: path == null
                        ? const Color(0xff8d948b)
                        : const Color(0xff374039),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          OutlinedButton(onPressed: onPressed, child: Text(buttonLabel)),
        ],
      ),
    );
  }
}

class InfoLine extends StatelessWidget {
  const InfoLine({super.key, required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 72,
          child:
              Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
        ),
        Expanded(
          child: Text(value, maxLines: 3, overflow: TextOverflow.ellipsis),
        ),
      ],
    );
  }
}

class SliderField extends StatelessWidget {
  const SliderField({
    super.key,
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.divisions,
    required this.suffix,
    required this.onChanged,
  });

  final String label;
  final double value;
  final double min;
  final double max;
  final int divisions;
  final String suffix;
  final ValueChanged<double>? onChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(child: Text(label)),
            Text(suffix, style: const TextStyle(fontWeight: FontWeight.w700)),
          ],
        ),
        Slider(
          value: value,
          min: min,
          max: max,
          divisions: divisions,
          onChanged: onChanged,
        ),
      ],
    );
  }
}

class ApiKeyTestResultsView extends StatelessWidget {
  const ApiKeyTestResultsView({super.key, required this.results});

  final List<ApiKeyTestResult> results;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: const Color(0xfffbfcfa),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xffd9ded6)),
      ),
      child: Column(
        children: [
          for (var i = 0; i < results.length; i++) ...[
            ApiKeyTestResultTile(result: results[i]),
            if (i != results.length - 1) const Divider(height: 1),
          ],
        ],
      ),
    );
  }
}

class ApiKeyTestResultTile extends StatelessWidget {
  const ApiKeyTestResultTile({super.key, required this.result});

  final ApiKeyTestResult result;

  @override
  Widget build(BuildContext context) {
    final color = _statusColor(result);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(_statusIcon(result), color: color, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  result.name,
                  style: TextStyle(fontWeight: FontWeight.w800, color: color),
                ),
                const SizedBox(height: 2),
                Text(
                  result.message,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12, height: 1.25),
                ),
                if (result.endpoint.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    result.endpoint,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Color(0xff687269),
                      fontSize: 11,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  IconData _statusIcon(ApiKeyTestResult result) {
    if (result.ok) {
      return Icons.check_circle_outline_rounded;
    }
    if (result.status == 'not_configured' || result.status == 'rate_limited') {
      return Icons.warning_amber_rounded;
    }
    return Icons.cancel_outlined;
  }

  Color _statusColor(ApiKeyTestResult result) {
    if (result.ok) {
      return const Color(0xff276b37);
    }
    if (result.status == 'not_configured' || result.status == 'rate_limited') {
      return const Color(0xffb54708);
    }
    return const Color(0xffb42318);
  }
}
