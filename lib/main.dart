import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;

void main() {
  runApp(const RefCheckerApp());
}

class RefCheckerApp extends StatelessWidget {
  const RefCheckerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'RefChecker',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xff1f7a6d),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xfff7f8f5),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(8)),
          ),
        ),
      ),
      home: const RefCheckerHomePage(),
    );
  }
}

enum RunState { idle, running, completed, failed }

class RunSettings {
  const RunSettings({
    required this.threshold,
    required this.delay,
    required this.email,
    required this.useOpenAlex,
    required this.useDblp,
    required this.useUrlVerify,
  });

  final double threshold;
  final double delay;
  final String email;
  final bool useOpenAlex;
  final bool useDblp;
  final bool useUrlVerify;
}

class RunSummary {
  const RunSummary({
    this.total = 0,
    this.found = 0,
    this.notFound = 0,
    this.needsReview = 0,
    this.skipped = 0,
    this.authorMismatch = 0,
    this.yearMismatch = 0,
    this.doiMismatch = 0,
    this.markdownPath = '',
    this.csvPath = '',
    this.outputDir = '',
  });

  final int total;
  final int found;
  final int notFound;
  final int needsReview;
  final int skipped;
  final int authorMismatch;
  final int yearMismatch;
  final int doiMismatch;
  final String markdownPath;
  final String csvPath;
  final String outputDir;

  RunSummary copyWith({
    int? total,
    int? found,
    int? notFound,
    int? needsReview,
    int? skipped,
    int? authorMismatch,
    int? yearMismatch,
    int? doiMismatch,
    String? markdownPath,
    String? csvPath,
    String? outputDir,
  }) {
    return RunSummary(
      total: total ?? this.total,
      found: found ?? this.found,
      notFound: notFound ?? this.notFound,
      needsReview: needsReview ?? this.needsReview,
      skipped: skipped ?? this.skipped,
      authorMismatch: authorMismatch ?? this.authorMismatch,
      yearMismatch: yearMismatch ?? this.yearMismatch,
      doiMismatch: doiMismatch ?? this.doiMismatch,
      markdownPath: markdownPath ?? this.markdownPath,
      csvPath: csvPath ?? this.csvPath,
      outputDir: outputDir ?? this.outputDir,
    );
  }

  factory RunSummary.fromJson(Map<String, dynamic> json) {
    return RunSummary(
      total: _asInt(json['total']),
      found: _asInt(json['found']),
      notFound: _asInt(json['not_found']),
      needsReview: _asInt(json['needs_review']),
      skipped: _asInt(json['skipped']),
      authorMismatch: _asInt(json['author_mismatch']),
      yearMismatch: _asInt(json['year_mismatch']),
      doiMismatch: _asInt(json['doi_mismatch']),
      markdownPath: _asString(json['markdown_path']),
      csvPath: _asString(json['csv_path']),
      outputDir: _asString(json['output_dir']),
    );
  }
}

class EntryResult {
  const EntryResult({
    required this.key,
    required this.title,
    required this.status,
    required this.needsReview,
    required this.source,
    required this.similarity,
    required this.reason,
  });

  final String key;
  final String title;
  final String status;
  final bool needsReview;
  final String source;
  final double? similarity;
  final String reason;

  factory EntryResult.fromJson(Map<String, dynamic> json) {
    final result = json['result'] is Map<String, dynamic>
        ? json['result'] as Map<String, dynamic>
        : const <String, dynamic>{};
    return EntryResult(
      key: _asString(result['key']),
      title: _asString(result['title']),
      status: _asString(result['status']),
      needsReview: _asString(result['needs_review']) == 'Yes',
      source: _asString(result['source']),
      similarity: _asDouble(result['similarity']),
      reason: _asString(result['reason']),
    );
  }
}

class RefCheckerHomePage extends StatefulWidget {
  const RefCheckerHomePage({super.key});

  @override
  State<RefCheckerHomePage> createState() => _RefCheckerHomePageState();
}

class _RefCheckerHomePageState extends State<RefCheckerHomePage> {
  final _emailController = TextEditingController();
  double _threshold = 0.85;
  double _delay = 0.2;
  bool _useOpenAlex = true;
  bool _useDblp = true;
  bool _useUrlVerify = true;
  bool _advancedOpen = false;

  String? _bibPath;
  String? _baseOutputDir;
  String? _activeOutputDir;
  String _currentKey = '';
  String _currentTitle = '';
  RunState _runState = RunState.idle;
  RunSummary _summary = const RunSummary();
  final List<EntryResult> _results = [];
  final List<String> _logs = [];
  final StringBuffer _fullLog = StringBuffer();
  IOSink? _logSink;
  String _logPath = '';
  Process? _process;

  bool get _canRun =>
      _runState != RunState.running &&
      _bibPath != null &&
      _baseOutputDir != null;

  double get _progress {
    if (_summary.total <= 0) {
      return 0;
    }
    final done = _results.length.clamp(0, _summary.total);
    return done / _summary.total;
  }

  @override
  void dispose() {
    _emailController.dispose();
    unawaited(_logSink?.flush());
    unawaited(_logSink?.close());
    _process?.kill();
    super.dispose();
  }

  Future<void> _pickBibFile() async {
    final path = await _pickFileWithNativeDialog();
    if (path == null) {
      return;
    }
    setState(() {
      _bibPath = path;
      _baseOutputDir ??= p.dirname(path);
    });
  }

  Future<void> _pickOutputDir() async {
    final path = await _pickDirectoryWithNativeDialog(
      initialDirectory: _baseOutputDir ?? (_bibPath == null ? null : p.dirname(_bibPath!)),
    );
    if (path == null) {
      return;
    }
    setState(() {
      _baseOutputDir = path;
    });
  }

  Future<void> _startRun() async {
    if (!_canRun) {
      return;
    }
    final bibPath = _bibPath!;
    final outputDir = _timestampedOutputDir(_baseOutputDir!);
    final settings = RunSettings(
      threshold: _threshold,
      delay: _delay,
      email: _emailController.text.trim(),
      useOpenAlex: _useOpenAlex,
      useDblp: _useDblp,
      useUrlVerify: _useUrlVerify,
    );

    setState(() {
      _runState = RunState.running;
      _summary = const RunSummary();
      _results.clear();
      _logs.clear();
      _fullLog.clear();
      _logPath = p.join(outputDir, 'run.log');
      _currentKey = '';
      _currentTitle = '';
      _activeOutputDir = outputDir;
    });

    try {
      await Directory(outputDir).create(recursive: true);
      await _logSink?.close();
      _logSink = File(_logPath).openWrite(mode: FileMode.writeOnly);
      final command = await _backendCommand();
      final args = _backendArgs(
        bibPath: bibPath,
        outputDir: outputDir,
        settings: settings,
        scriptPath: command.scriptPath,
      );
      _appendLog('启动校验：${p.basename(bibPath)}');
      _appendLog('输出目录：$outputDir');
      final process = await Process.start(
        command.executable,
        args,
        runInShell: false,
        environment: const {
          'PYTHONUTF8': '1',
          'PYTHONIOENCODING': 'utf-8',
        },
      );
      _process = process;
      final stdoutDone = _listenStdout(process.stdout);
      final stderrDone = _listenStderr(process.stderr);
      final exitCode = await process.exitCode;
      await Future.wait([stdoutDone, stderrDone]);
      _process = null;
      if (!mounted) {
        return;
      }
      setState(() {
        _runState = exitCode == 0 ? RunState.completed : RunState.failed;
      });
      if (exitCode != 0) {
        _appendLog('后端进程退出码：$exitCode');
      }
      await _finishLogFile();
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _runState = RunState.failed;
      });
      _appendLog('启动失败：$error');
      await _finishLogFile();
    }
  }

  Future<void> _listenStdout(Stream<List<int>> stream) {
    return stream
        .transform(const Utf8Decoder(allowMalformed: true))
        .transform(const LineSplitter())
        .listen(
          _handleBackendLine,
          onError: (Object error) => _appendLog('stdout 解码失败：$error'),
        )
        .asFuture<void>();
  }

  Future<void> _listenStderr(Stream<List<int>> stream) {
    return stream
        .transform(const Utf8Decoder(allowMalformed: true))
        .transform(const LineSplitter())
        .listen((line) {
      if (line.trim().isNotEmpty) {
        _appendLog(line);
      }
    }, onError: (Object error) => _appendLog('stderr 解码失败：$error')).asFuture<void>();
  }

  void _handleBackendLine(String line) {
    if (line.trim().isEmpty) {
      return;
    }
    try {
      final decoded = jsonDecode(line);
      if (decoded is! Map<String, dynamic>) {
        _appendLog(line);
        return;
      }
      final type = _asString(decoded['type']);
      switch (type) {
        case 'started':
          setState(() {
            _summary = _summary.copyWith(total: _asInt(decoded['total']));
          });
          _appendLog('解析到 ${_summary.total} 条文献');
          break;
        case 'entry_started':
          setState(() {
            _currentKey = _asString(decoded['key']);
            _currentTitle = _asString(decoded['title']);
          });
          break;
        case 'entry_finished':
          final result = EntryResult.fromJson(decoded);
          setState(() {
            _results.insert(0, result);
          });
          _appendLog(_formatResultLog(result));
          break;
        case 'summary':
          setState(() {
            _summary = RunSummary.fromJson(decoded);
          });
          _appendLog('校验完成：找到 ${_summary.found}，未找到 ${_summary.notFound}，需复核 ${_summary.needsReview}');
          break;
        case 'error':
          setState(() {
            _runState = RunState.failed;
          });
          _appendLog('错误：${_asString(decoded['message'])}');
          break;
        default:
          _appendLog(line);
      }
    } catch (_) {
      _appendLog(line);
    }
  }

  void _appendLog(String message) {
    if (!mounted || message.trim().isEmpty) {
      return;
    }
    final stamped = '[${DateTime.now().toIso8601String()}] $message';
    _fullLog.writeln(stamped);
    _logSink?.writeln(stamped);
    setState(() {
      _logs.insert(0, message);
      if (_logs.length > 200) {
        _logs.removeRange(200, _logs.length);
      }
    });
  }

  Future<void> _finishLogFile() async {
    final sink = _logSink;
    _logSink = null;
    if (sink != null) {
      await sink.flush();
      await sink.close();
    }
  }

  Future<_BackendCommand> _backendCommand() async {
    final appDir = File(Platform.resolvedExecutable).parent.path;
    final executableName =
        Platform.isWindows ? 'refchecker_backend.exe' : 'refchecker_backend';
    final candidates = <String>[
      p.join(appDir, executableName),
      p.join(appDir, 'backend', executableName),
      p.join(Directory.current.path, 'backend', executableName),
    ];
    if (Platform.isMacOS) {
      candidates.add(p.normalize(p.join(appDir, '..', 'Resources', 'backend', executableName)));
      candidates.add(p.normalize(p.join(appDir, '..', 'Resources', executableName)));
    }
    for (final candidate in candidates) {
      if (await File(candidate).exists()) {
        return _BackendCommand(executable: candidate);
      }
    }
    final scriptPath = p.join(appDir, 'check_bib_crossref.py');
    return _BackendCommand(executable: _pythonExecutable(), scriptPath: scriptPath);
  }

  String _pythonExecutable() {
    if (Platform.isWindows) {
      return 'python';
    }
    return 'python3';
  }

  List<String> _backendArgs({
    required String bibPath,
    required String outputDir,
    required RunSettings settings,
    String? scriptPath,
  }) {
    final args = <String>[];
    if (scriptPath != null) {
      args.add(scriptPath);
    }
    args.addAll([
      bibPath,
      '--jsonl-progress',
      '--output-dir',
      outputDir,
      '--threshold',
      settings.threshold.toStringAsFixed(2),
      '--delay',
      settings.delay.toStringAsFixed(2),
    ]);
    if (settings.email.isNotEmpty) {
      args.addAll(['--email', settings.email]);
    }
    if (!settings.useOpenAlex) {
      args.add('--no-openalex');
    }
    if (!settings.useDblp) {
      args.add('--no-dblp');
    }
    if (!settings.useUrlVerify) {
      args.add('--no-url-verify');
    }
    return args;
  }

  String _timestampedOutputDir(String baseDir) {
    final now = DateTime.now();
    final stamp = [
      now.year.toString().padLeft(4, '0'),
      now.month.toString().padLeft(2, '0'),
      now.day.toString().padLeft(2, '0'),
      '_',
      now.hour.toString().padLeft(2, '0'),
      now.minute.toString().padLeft(2, '0'),
      now.second.toString().padLeft(2, '0'),
    ].join();
    return p.join(baseDir, 'refchecker_$stamp');
  }

  String _formatResultLog(EntryResult result) {
    final sim = result.similarity == null
        ? ''
        : ' ${(result.similarity! * 100).round()}%';
    final review = result.needsReview ? ' 需复核' : '';
    final source = result.source.isEmpty ? '' : ' ${result.source}';
    final reason = result.reason.isEmpty ? '' : ' ${result.reason}';
    return '${result.key}: ${result.status}$source$sim$review$reason';
  }

  Future<void> _openPath(String path) async {
    if (path.isEmpty) {
      return;
    }
    try {
      if (Platform.isWindows) {
        await Process.run('explorer', [path]);
      } else if (Platform.isMacOS) {
        await Process.run('open', [path]);
      } else {
        await Process.run('xdg-open', [path]);
      }
    } catch (error) {
      _appendLog('无法打开：$path ($error)');
    }
  }

  Future<void> _copyLogs() async {
    final text = _fullLog.isEmpty ? _logs.reversed.join('\n') : _fullLog.toString();
    if (text.trim().isEmpty) {
      _appendLog('暂无日志可复制');
      return;
    }
    await Clipboard.setData(ClipboardData(text: text));
    _appendLog('日志已复制到剪贴板');
  }

  Future<String?> _pickFileWithNativeDialog() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['bib', 'docx'],
    );
    if (result == null || result.files.isEmpty) return null;
    return result.files.single.path;
  }

  Future<String?> _pickDirectoryWithNativeDialog({String? initialDirectory}) async {
    final path = await FilePicker.platform.getDirectoryPath(
      initialDirectory: initialDirectory,
    );
    return path;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _HeaderBar(
              canRun: _canRun,
              runState: _runState,
              onRun: _startRun,
            ),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final narrow = constraints.maxWidth < 940;
                  final controlPanel = _ControlPanel(
                    bibPath: _bibPath,
                    outputDir: _baseOutputDir,
                    activeOutputDir: _activeOutputDir,
                    runState: _runState,
                    advancedOpen: _advancedOpen,
                    threshold: _threshold,
                    delay: _delay,
                    emailController: _emailController,
                    useOpenAlex: _useOpenAlex,
                    useDblp: _useDblp,
                    useUrlVerify: _useUrlVerify,
                    onPickBib: _pickBibFile,
                    onPickOutputDir: _pickOutputDir,
                    onAdvancedChanged: (value) => setState(() => _advancedOpen = value),
                    onThresholdChanged: (value) => setState(() => _threshold = value),
                    onDelayChanged: (value) => setState(() => _delay = value),
                    onUseOpenAlexChanged: (value) => setState(() => _useOpenAlex = value),
                    onUseDblpChanged: (value) => setState(() => _useDblp = value),
                    onUseUrlVerifyChanged: (value) => setState(() => _useUrlVerify = value),
                  );
                  final resultsPanel = _ResultsPanel(
                    runState: _runState,
                    progress: _progress,
                    summary: _summary,
                    currentKey: _currentKey,
                    currentTitle: _currentTitle,
                    results: _results,
                    logs: _logs,
                    logPath: _logPath,
                    onOpenMarkdown: () => _openPath(_summary.markdownPath),
                    onOpenCsv: () => _openPath(_summary.csvPath),
                    onOpenOutputDir: () => _openPath(
                      _summary.outputDir.isNotEmpty
                          ? _summary.outputDir
                          : (_activeOutputDir ?? ''),
                    ),
                    onOpenLog: () => _openPath(_logPath),
                    onCopyLogs: _copyLogs,
                  );
                  if (narrow) {
                    return ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        controlPanel,
                        const SizedBox(height: 16),
                        SizedBox(height: 680, child: resultsPanel),
                      ],
                    );
                  }
                  return Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        SizedBox(width: 380, child: controlPanel),
                        const SizedBox(width: 16),
                        Expanded(child: resultsPanel),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BackendCommand {
  const _BackendCommand({required this.executable, this.scriptPath});

  final String executable;
  final String? scriptPath;
}

class _HeaderBar extends StatelessWidget {
  const _HeaderBar({
    required this.canRun,
    required this.runState,
    required this.onRun,
  });

  final bool canRun;
  final RunState runState;
  final VoidCallback onRun;

  @override
  Widget build(BuildContext context) {
    final running = runState == RunState.running;
    return Container(
      height: 76,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: Color(0xffd9ded6))),
      ),
      child: Row(
        children: [
          const Icon(Icons.fact_check_outlined, size: 32),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'RefChecker',
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
                ),
                Text('BibTeX / DOCX 文献真实性与元数据一致性核验'),
              ],
            ),
          ),
          FilledButton.icon(
            onPressed: canRun ? onRun : null,
            icon: running
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.play_arrow_rounded),
            label: Text(running ? '校验中' : '开始校验'),
          ),
        ],
      ),
    );
  }
}

class _ControlPanel extends StatelessWidget {
  const _ControlPanel({
    required this.bibPath,
    required this.outputDir,
    required this.activeOutputDir,
    required this.runState,
    required this.advancedOpen,
    required this.threshold,
    required this.delay,
    required this.emailController,
    required this.useOpenAlex,
    required this.useDblp,
    required this.useUrlVerify,
    required this.onPickBib,
    required this.onPickOutputDir,
    required this.onAdvancedChanged,
    required this.onThresholdChanged,
    required this.onDelayChanged,
    required this.onUseOpenAlexChanged,
    required this.onUseDblpChanged,
    required this.onUseUrlVerifyChanged,
  });

  final String? bibPath;
  final String? outputDir;
  final String? activeOutputDir;
  final RunState runState;
  final bool advancedOpen;
  final double threshold;
  final double delay;
  final TextEditingController emailController;
  final bool useOpenAlex;
  final bool useDblp;
  final bool useUrlVerify;
  final VoidCallback onPickBib;
  final VoidCallback onPickOutputDir;
  final ValueChanged<bool> onAdvancedChanged;
  final ValueChanged<double> onThresholdChanged;
  final ValueChanged<double> onDelayChanged;
  final ValueChanged<bool> onUseOpenAlexChanged;
  final ValueChanged<bool> onUseDblpChanged;
  final ValueChanged<bool> onUseUrlVerifyChanged;

  @override
  Widget build(BuildContext context) {
    final disabled = runState == RunState.running;
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
            const Text(
              '输入',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            _PathTile(
              icon: Icons.upload_file_outlined,
              title: '文献文件 (.bib / .docx)',
              path: bibPath,
              buttonLabel: '选择',
              onPressed: disabled ? null : onPickBib,
            ),
            const SizedBox(height: 12),
            _PathTile(
              icon: Icons.folder_outlined,
              title: '结果保存位置',
              path: outputDir,
              buttonLabel: '选择',
              onPressed: disabled ? null : onPickOutputDir,
            ),
            if (activeOutputDir != null) ...[
              const SizedBox(height: 12),
              _InfoLine(label: '本次输出', value: activeOutputDir!),
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
              _SliderField(
                label: '标题相似度阈值',
                value: threshold,
                min: 0.60,
                max: 0.98,
                divisions: 38,
                suffix: '${(threshold * 100).round()}%',
                onChanged: disabled ? null : onThresholdChanged,
              ),
              const SizedBox(height: 8),
              _SliderField(
                label: '请求间隔',
                value: delay,
                min: 0,
                max: 2,
                divisions: 40,
                suffix: '${delay.toStringAsFixed(2)}s',
                onChanged: disabled ? null : onDelayChanged,
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
              const SizedBox(height: 8),
              CheckboxListTile(
                value: useOpenAlex,
                onChanged: disabled
                    ? null
                    : (value) => onUseOpenAlexChanged(value ?? true),
                contentPadding: EdgeInsets.zero,
                title: const Text('启用 OpenAlex'),
              ),
              CheckboxListTile(
                value: useDblp,
                onChanged:
                    disabled ? null : (value) => onUseDblpChanged(value ?? true),
                contentPadding: EdgeInsets.zero,
                title: const Text('启用 DBLP'),
              ),
              CheckboxListTile(
                value: useUrlVerify,
                onChanged:
                    disabled ? null : (value) => onUseUrlVerifyChanged(value ?? true),
                contentPadding: EdgeInsets.zero,
                title: const Text('启用 URL 验证 (HuggingFace / GitHub / 网页)'),
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

class _PathTile extends StatelessWidget {
  const _PathTile({
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
                Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
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

class _InfoLine extends StatelessWidget {
  const _InfoLine({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 72,
          child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
        ),
        Expanded(
          child: Text(value, maxLines: 3, overflow: TextOverflow.ellipsis),
        ),
      ],
    );
  }
}

class _SliderField extends StatelessWidget {
  const _SliderField({
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

class _ResultsPanel extends StatelessWidget {
  const _ResultsPanel({
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
                _StateChip(runState: runState),
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
                  : '$currentKey  ${_trim(currentTitle, 110)}',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                _MetricCard(label: '总数', value: summary.total),
                _MetricCard(label: '找到', value: summary.found),
                _MetricCard(label: '未找到', value: summary.notFound),
                _MetricCard(label: '需复核', value: summary.needsReview),
                _MetricCard(label: '跳过', value: summary.skipped),
                _MetricCard(label: '作者问题', value: summary.authorMismatch),
                _MetricCard(label: '年份问题', value: summary.yearMismatch),
                _MetricCard(label: 'DOI 问题', value: summary.doiMismatch),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                FilledButton.tonalIcon(
                  onPressed:
                      summary.markdownPath.isEmpty ? null : onOpenMarkdown,
                  icon: const Icon(Icons.description_outlined),
                  label: const Text('报告'),
                ),
                const SizedBox(width: 8),
                FilledButton.tonalIcon(
                  onPressed: summary.csvPath.isEmpty ? null : onOpenCsv,
                  icon: const Icon(Icons.table_chart_outlined),
                  label: const Text('CSV'),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: summary.outputDir.isEmpty ? null : onOpenOutputDir,
                  icon: const Icon(Icons.folder_open_rounded),
                  label: const Text('目录'),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: logPath.isEmpty ? null : onOpenLog,
                  icon: const Icon(Icons.article_outlined),
                  label: const Text('日志'),
                ),
                const SizedBox(width: 8),
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
                    child: _ResultList(results: results),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _LogList(logs: logs),
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

class _StateChip extends StatelessWidget {
  const _StateChip({required this.runState});

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

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.label, required this.value});

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

class _ResultList extends StatelessWidget {
  const _ResultList({required this.results});

  final List<EntryResult> results;

  @override
  Widget build(BuildContext context) {
    return _PanelFrame(
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
                  leading: Icon(_statusIcon(item.status, item.needsReview)),
                  title: Text(
                    item.key,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: Text(
                    _trim(item.title.isEmpty ? item.reason : item.title, 90),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing: Text(_statusLabel(item)),
                );
              },
            ),
    );
  }

  IconData _statusIcon(String status, bool needsReview) {
    if (status == 'found' && !needsReview) {
      return Icons.check_circle_outline_rounded;
    }
    if (status == 'found' || needsReview) {
      return Icons.error_outline_rounded;
    }
    if (status == 'skipped') {
      return Icons.skip_next_outlined;
    }
    return Icons.cancel_outlined;
  }

  String _statusLabel(EntryResult item) {
    final source = item.source.isEmpty ? item.status : item.source;
    final sim = item.similarity == null
        ? ''
        : ' ${(item.similarity! * 100).round()}%';
    return '$source$sim';
  }
}

class _LogList extends StatelessWidget {
  const _LogList({required this.logs});

  final List<String> logs;

  @override
  Widget build(BuildContext context) {
    return _PanelFrame(
      title: '日志',
      child: logs.isEmpty
          ? const Center(child: Text('暂无日志'))
          : ListView.separated(
              reverse: true,
              itemCount: logs.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, index) {
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  child: SelectableText(logs[index]),
                );
              },
            ),
    );
  }
}

class _PanelFrame extends StatelessWidget {
  const _PanelFrame({required this.title, required this.child});

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
            child: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
          ),
          const Divider(height: 1),
          Expanded(child: child),
        ],
      ),
    );
  }
}

int _asInt(dynamic value) {
  if (value is int) {
    return value;
  }
  if (value is num) {
    return value.toInt();
  }
  return int.tryParse('$value') ?? 0;
}

double? _asDouble(dynamic value) {
  if (value is double) {
    return value;
  }
  if (value is int) {
    return value.toDouble();
  }
  if (value is String && value.trim().isNotEmpty) {
    return double.tryParse(value);
  }
  return null;
}

String _asString(dynamic value) {
  if (value == null) {
    return '';
  }
  return '$value';
}

String _trim(String text, int maxLength) {
  if (text.length <= maxLength) {
    return text;
  }
  return '${text.substring(0, maxLength - 3)}...';
}
