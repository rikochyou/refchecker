import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;

import 'models.dart';
import 'utils.dart';
import 'app_info.dart';
import 'widgets/header_bar.dart';
import 'widgets/control_panel.dart';
import 'widgets/results_panel.dart';

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
        fontFamily: 'NotoSansSC',
        fontFamilyFallback: const [
          'Segoe UI Emoji',
          'Microsoft YaHei UI',
          'Arial',
        ],
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

String _settingsPath() {
  final appData = Platform.environment['APPDATA'] ??
      Platform.environment['HOME'] ??
      Directory.current.path;
  return p.join(appData, 'RefChecker', 'settings.json');
}

class RefCheckerHomePage extends StatefulWidget {
  const RefCheckerHomePage({super.key});

  @override
  State<RefCheckerHomePage> createState() => _RefCheckerHomePageState();
}

class _RefCheckerHomePageState extends State<RefCheckerHomePage> {
  static const _nativeDialogs = MethodChannel('refchecker/native_dialogs');
  static const _httpServerHost = '127.0.0.1';
  static const _httpServerPort = 8765;

  final _emailController = TextEditingController();
  final _textController = TextEditingController();
  double _threshold = 0.85;
  double _delay = defaultDelaySeconds;
  bool _useCrossref = true;
  bool _useOpenAlex = true;
  bool _useSemanticScholar = true;
  bool _useArxiv = true;
  bool _usePubMed = true;
  bool _useDblp = true;
  bool _useUrlVerify = true;
  bool _useSpringer = true;
  bool _useIeee = true;
  bool _useCore = true;
  bool _advancedOpen = false;
  bool _useTextMode = false;
  List<String> _sourceOrder = defaultSourceOrder();

  final List<CustomApiSourceEntry> _customApiSources = [];
  int _customSourceIdSeed = 0;
  bool _settingsLoaded = false;
  Timer? _saveTimer;

  static const _sourceNames = <String, String>{
    'crossref': 'CrossRef',
    'openalex': 'OpenAlex',
    'semantic-scholar': 'Semantic Scholar',
    'arxiv': 'arXiv',
    'pubmed': 'PubMed',
    'dblp': 'DBLP',
    'url': 'URL 验证',
    'springer': 'Springer Nature',
    'ieee': 'IEEE Xplore',
    'core': 'CORE',
  };

  static const _apiBackedSourceKeys = {'springer', 'ieee', 'core'};

  String? _apiSourceKeyForEntry(CustomApiSourceEntry entry) {
    if (entry.isCustomRest) {
      return 'custom:${entry.id}';
    }
    final name = entry.nameController.text.trim().toLowerCase();
    final envVar = entry.envVarController.text.trim().toUpperCase();
    final envLower = entry.envVarController.text.trim().toLowerCase();
    final combined = '$name $envLower';
    if (envVar == 'REFCHECKER_SPRINGER_API_KEY' ||
        combined.contains('springer')) {
      return 'springer';
    }
    if (envVar == 'REFCHECKER_IEEE_API_KEY' || combined.contains('ieee')) {
      return 'ieee';
    }
    if (envVar == 'REFCHECKER_CORE_API_KEY' ||
        name == 'core' ||
        combined.contains('core_api_key')) {
      return 'core';
    }
    return null;
  }

  bool _isCustomSourceKey(String key) => key.startsWith('custom:');

  CustomApiSourceEntry? _customEntryForKey(String key) {
    if (!_isCustomSourceKey(key)) {
      return null;
    }
    final id = key.substring('custom:'.length);
    for (final entry in _customApiSources) {
      if (entry.id == id) {
        return entry;
      }
    }
    return null;
  }

  bool _customApiSourceEnabled(String key) {
    if (_isCustomSourceKey(key)) {
      final entry = _customEntryForKey(key);
      return entry != null && entry.enabled && entry.isCustomRest;
    }
    if (!_apiBackedSourceKeys.contains(key)) return true;
    return _customApiSources
        .any((entry) => entry.enabled && _apiSourceKeyForEntry(entry) == key);
  }

  String? _customApiSourceName(String key) {
    if (_isCustomSourceKey(key)) {
      final entry = _customEntryForKey(key);
      final name = entry?.nameController.text.trim() ?? '';
      return name.isEmpty ? 'Custom REST API' : name;
    }
    for (final entry in _customApiSources) {
      if (!entry.enabled || _apiSourceKeyForEntry(entry) != key) {
        continue;
      }
      final name = entry.nameController.text.trim();
      if (name.isNotEmpty) {
        return name;
      }
    }
    return null;
  }

  bool _isSourceVisible(String key) {
    if (_isCustomSourceKey(key)) {
      return _customApiSourceEnabled(key);
    }
    if (!_apiBackedSourceKeys.contains(key)) {
      return true;
    }
    return _customApiSourceEnabled(key);
  }

  List<String> _completeSourceOrder() {
    final order = [..._sourceOrder];
    for (final key in defaultSourceOrder()) {
      if (!order.contains(key)) {
        order.add(key);
      }
    }
    for (final entry in _customApiSources) {
      final key = _apiSourceKeyForEntry(entry);
      if (key != null && key.startsWith('custom:') && !order.contains(key)) {
        order.add(key);
      }
    }
    return order;
  }

  List<String> _visibleSourceOrder() =>
      _completeSourceOrder().where(_isSourceVisible).toList();

  Map<String, String> _sourceNamesForPanel() {
    final names = Map<String, String>.from(_sourceNames);
    for (final key in _apiBackedSourceKeys) {
      final customName = _customApiSourceName(key);
      if (customName != null) {
        names[key] = customName;
      }
    }
    for (final entry in _customApiSources) {
      final key = _apiSourceKeyForEntry(entry);
      if (key != null && key.startsWith('custom:')) {
        final name = entry.nameController.text.trim();
        names[key] = name.isEmpty ? 'Custom REST API' : name;
      }
    }
    return names;
  }

  String _newCustomSourceId([String prefix = 'custom']) {
    _customSourceIdSeed += 1;
    return '${prefix}_${DateTime.now().microsecondsSinceEpoch}_$_customSourceIdSeed';
  }

  String _legacyRestProfileJsonFromSource(CustomApiSource source) {
    if (source.restProfileJson.trim().isNotEmpty) {
      return source.restProfileJson;
    }
    if (source.endpoint.trim().isEmpty) {
      return '';
    }
    final profile = <String, dynamic>{
      'endpoint': source.endpoint,
      'method': source.method,
      'authType': source.authType,
      'apiKeyParam': source.apiKeyParam,
      'apiKeyHeader': source.apiKeyHeader,
      'queryParams': _decodeJsonObjectText(source.queryParams),
      'headers': _decodeJsonObjectText(source.headers),
      'resultsPath': source.resultsPath,
      'titlePath': source.titlePath,
      'authorsPath': source.authorsPath,
      'yearPath': source.yearPath,
      'doiPath': source.doiPath,
      'urlPath': source.urlPath,
      'venuePath': source.venuePath,
      'typePath': source.typePath,
    };
    return const JsonEncoder.withIndent('  ').convert(profile);
  }

  Object _decodeJsonObjectText(String value) {
    if (value.trim().isEmpty) {
      return <String, dynamic>{};
    }
    try {
      final decoded = jsonDecode(value);
      return decoded is Map ? decoded : <String, dynamic>{};
    } catch (_) {
      return <String, dynamic>{};
    }
  }

  CustomApiSourceEntry _entryFromSource(CustomApiSource source,
      {String? fallbackId}) {
    return CustomApiSourceEntry(
      id: source.id.isEmpty ? (fallbackId ?? _newCustomSourceId()) : source.id,
      nameController: TextEditingController(text: source.name),
      keyController: TextEditingController(text: source.apiKey),
      envVarController: TextEditingController(text: source.envVar),
      endpointController: TextEditingController(text: source.endpoint),
      methodController: TextEditingController(text: source.method),
      authTypeController: TextEditingController(text: source.authType),
      apiKeyParamController: TextEditingController(text: source.apiKeyParam),
      apiKeyHeaderController: TextEditingController(text: source.apiKeyHeader),
      queryParamsController: TextEditingController(text: source.queryParams),
      headersController: TextEditingController(text: source.headers),
      restProfileJsonController:
          TextEditingController(text: _legacyRestProfileJsonFromSource(source)),
      resultsPathController: TextEditingController(text: source.resultsPath),
      titlePathController: TextEditingController(text: source.titlePath),
      authorsPathController: TextEditingController(text: source.authorsPath),
      yearPathController: TextEditingController(text: source.yearPath),
      doiPathController: TextEditingController(text: source.doiPath),
      urlPathController: TextEditingController(text: source.urlPath),
      venuePathController: TextEditingController(text: source.venuePath),
      typePathController: TextEditingController(text: source.typePath),
      enabled: source.enabled,
      searchEnabled: source.searchEnabled,
    );
  }

  bool _isSourceEnabled(String key) => switch (key) {
        'crossref' => _useCrossref,
        'openalex' => _useOpenAlex,
        'semantic-scholar' => _useSemanticScholar,
        'arxiv' => _useArxiv,
        'pubmed' => _usePubMed,
        'dblp' => _useDblp,
        'url' => _useUrlVerify,
        'springer' => _useSpringer && _customApiSourceEnabled('springer'),
        'ieee' => _useIeee && _customApiSourceEnabled('ieee'),
        'core' => _useCore && _customApiSourceEnabled('core'),
        _ when _isCustomSourceKey(key) =>
          (_customEntryForKey(key)?.enabled ?? false) &&
              (_customEntryForKey(key)?.searchEnabled ?? false),
        _ => true,
      };

  void _setSourceEnabled(String key, bool value) {
    switch (key) {
      case 'crossref':
        _useCrossref = value;
      case 'openalex':
        _useOpenAlex = value;
      case 'semantic-scholar':
        _useSemanticScholar = value;
      case 'arxiv':
        _useArxiv = value;
      case 'pubmed':
        _usePubMed = value;
      case 'dblp':
        _useDblp = value;
      case 'url':
        _useUrlVerify = value;
      case 'springer':
        _useSpringer = value;
      case 'ieee':
        _useIeee = value;
      case 'core':
        _useCore = value;
      default:
        if (_isCustomSourceKey(key)) {
          final entry = _customEntryForKey(key);
          if (entry != null) {
            entry.searchEnabled = value;
          }
        }
    }
  }

  String? _bibPath;
  String? _baseOutputDir;
  String? _activeOutputDir;
  String _currentKey = '';
  String _currentTitle = '';
  RunState _runState = RunState.idle;
  RunSummary _summary = const RunSummary();
  final List<EntryResult> _results = [];
  final List<String> _logs = [];
  final List<ApiKeyTestResult> _apiKeyTestResults = [];
  final ValueNotifier<int> _apiKeyTestRevision = ValueNotifier<int>(0);
  final Set<String> _testingApiSourceIds = <String>{};
  final StringBuffer _fullLog = StringBuffer();
  IOSink? _logSink;
  String _logPath = '';
  Process? _process;
  Process? _httpServerProcess;
  bool get _testingApiKeys => _testingApiSourceIds.isNotEmpty;

  bool get _canRun =>
      _runState != RunState.running &&
      !_testingApiKeys &&
      _baseOutputDir != null &&
      (_useTextMode
          ? _textController.text.trim().isNotEmpty
          : _bibPath != null);

  double get _progress {
    if (_summary.total <= 0) {
      return 0;
    }
    final done = _results.length.clamp(0, _summary.total);
    return done / _summary.total;
  }

  @override
  void initState() {
    super.initState();
    _emailController.addListener(_scheduleSaveSettings);
    _textController.addListener(_scheduleSaveSettings);
    unawaited(_loadSettings().then((_) => _ensureHttpServerStarted()));
  }

  @override
  void dispose() {
    _saveTimer?.cancel();
    _emailController.dispose();
    _textController.dispose();
    for (final entry in _customApiSources) {
      entry.dispose();
    }
    _apiKeyTestRevision.dispose();
    unawaited(_logSink?.flush());
    unawaited(_logSink?.close());
    _process?.kill();
    _httpServerProcess?.kill();
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
      initialDirectory:
          _baseOutputDir ?? (_bibPath == null ? null : p.dirname(_bibPath!)),
    );
    if (path == null) {
      return;
    }
    setState(() {
      _baseOutputDir = path;
    });
  }

  // ── settings persistence ──

  Future<void> _loadSettings() async {
    try {
      final file = File(_settingsPath());
      if (!await file.exists()) {
        _ensureDefaultApiSources();
        _settingsLoaded = true;
        return;
      }
      final json = jsonDecode(await file.readAsString());
      if (json is! Map<String, dynamic>) {
        _ensureDefaultApiSources();
        _settingsLoaded = true;
        return;
      }
      final settings = RunSettings.fromJson(json);
      setState(() {
        _threshold = settings.threshold;
        _delay = clampDelaySeconds(settings.delay);
        _emailController.text = settings.email;
        _useCrossref = settings.useCrossref;
        _useOpenAlex = settings.useOpenAlex;
        _useSemanticScholar = settings.useSemanticScholar;
        _useArxiv = settings.useArxiv;
        _usePubMed = settings.usePubMed;
        _useDblp = settings.useDblp;
        _useUrlVerify = settings.useUrlVerify;
        _useSpringer = settings.useSpringer;
        _useIeee = settings.useIeee;
        _useCore = settings.useCore;
        if (settings.sourceOrder.isNotEmpty) {
          _sourceOrder = settings.sourceOrder;
        }
        for (final entry in _customApiSources) {
          entry.dispose();
        }
        _customApiSources.clear();
        for (final src in settings.customApiSources) {
          final entry = _entryFromSource(src);
          _attachCustomApiSourceListeners(entry);
          _customApiSources.add(entry);
        }
        if (_customApiSources.isEmpty) {
          _ensureDefaultApiSources();
        }
      });
      _settingsLoaded = true;
    } catch (_) {
      _ensureDefaultApiSources();
      _settingsLoaded = true;
    }
  }

  void _ensureDefaultApiSources() {
    const defaults = [
      ('springer', 'Springer Nature', 'REFCHECKER_SPRINGER_API_KEY'),
      ('ieee', 'IEEE Xplore', 'REFCHECKER_IEEE_API_KEY'),
      ('core', 'CORE', 'REFCHECKER_CORE_API_KEY'),
    ];
    for (final (id, name, envVar) in defaults) {
      final entry = _entryFromSource(
        CustomApiSource(
          id: id,
          name: name,
          apiKey: '',
          envVar: envVar,
        ),
        fallbackId: id,
      );
      _attachCustomApiSourceListeners(entry);
      _customApiSources.add(entry);
    }
  }

  void _attachCustomApiSourceListeners(CustomApiSourceEntry entry) {
    void listener() {
      _scheduleSaveSettings();
      if (mounted) {
        setState(() {});
      }
    }

    entry.nameController.addListener(listener);
    entry.keyController.addListener(listener);
    entry.envVarController.addListener(listener);
    entry.endpointController.addListener(listener);
    entry.methodController.addListener(listener);
    entry.authTypeController.addListener(listener);
    entry.apiKeyParamController.addListener(listener);
    entry.apiKeyHeaderController.addListener(listener);
    entry.queryParamsController.addListener(listener);
    entry.headersController.addListener(listener);
    entry.restProfileJsonController.addListener(listener);
    entry.resultsPathController.addListener(listener);
    entry.titlePathController.addListener(listener);
    entry.authorsPathController.addListener(listener);
    entry.yearPathController.addListener(listener);
    entry.doiPathController.addListener(listener);
    entry.urlPathController.addListener(listener);
    entry.venuePathController.addListener(listener);
    entry.typePathController.addListener(listener);
  }

  void _scheduleSaveSettings() {
    if (!_settingsLoaded) return;
    _saveTimer?.cancel();
    _saveTimer = Timer(const Duration(milliseconds: 500), _saveSettings);
  }

  Future<void> _saveSettings() async {
    if (!_settingsLoaded) return;
    try {
      final file = File(_settingsPath());
      await file.parent.create(recursive: true);
      final settings = _currentSettings();
      await file.writeAsString(
          const JsonEncoder.withIndent('  ').convert(settings.toJson()));
    } catch (_) {}
  }

  // ── data source toggles ──

  void _selectAllSources() {
    setState(() {
      for (final key in _visibleSourceOrder()) {
        _setSourceEnabled(key, true);
      }
    });
    _scheduleSaveSettings();
  }

  void _deselectAllSources() {
    setState(() {
      for (final key in _visibleSourceOrder()) {
        _setSourceEnabled(key, false);
      }
    });
    _scheduleSaveSettings();
  }

  void _onReorderSources(int oldIndex, int newIndex) {
    setState(() {
      final visibleOrder = _visibleSourceOrder();
      if (oldIndex < 0 ||
          oldIndex >= visibleOrder.length ||
          newIndex < 0 ||
          newIndex > visibleOrder.length) {
        return;
      }
      final item = visibleOrder[oldIndex];
      final visibleAfterMove = [...visibleOrder]..removeAt(oldIndex);
      _sourceOrder.remove(item);
      final insertIndex = newIndex >= visibleAfterMove.length
          ? _sourceOrder.length
          : _sourceOrder.indexOf(visibleAfterMove[newIndex]);
      _sourceOrder.insert(
          insertIndex < 0 ? _sourceOrder.length : insertIndex, item);
    });
    _scheduleSaveSettings();
  }

  // ── custom API sources ──

  void _addCustomApiSource() {
    final entry = _entryFromSource(
      CustomApiSource(
        id: _newCustomSourceId(),
        name: '',
        apiKey: '',
        envVar: '',
        enabled: false,
        searchEnabled: true,
      ),
    );
    _attachCustomApiSourceListeners(entry);
    setState(() => _customApiSources.add(entry));
    _scheduleSaveSettings();
  }

  void _removeCustomApiSource(int index) {
    if (index < 0 || index >= _customApiSources.length) return;
    final entry = _customApiSources.removeAt(index);
    entry.dispose();
    setState(() {});
    _scheduleSaveSettings();
  }

  void _setCustomApiSourceEnabled(int index, bool value) {
    if (index < 0 || index >= _customApiSources.length) return;
    setState(() {
      final entry = _customApiSources[index];
      entry.enabled = value;
      if (value) {
        entry.searchEnabled = true;
      }
      final key = _apiSourceKeyForEntry(entry);
      if (key != null) {
        _setSourceEnabled(key, value);
        if (!_sourceOrder.contains(key)) {
          _sourceOrder.add(key);
        }
      }
    });
    _scheduleSaveSettings();
  }

  bool _isTestingCustomApiSource(int index) {
    if (index < 0) {
      return _testingApiKeys;
    }
    if (index < 0 || index >= _customApiSources.length) {
      return false;
    }
    return _testingApiSourceIds.contains(_customApiSources[index].id);
  }

  ApiKeyTestResult? _apiKeyTestResultForCustomApiSource(int index) {
    if (index < 0 || index >= _customApiSources.length) {
      return null;
    }
    final key = _apiSourceKeyForEntry(_customApiSources[index]);
    if (key == null) {
      return null;
    }
    for (final result in _apiKeyTestResults.reversed) {
      if (result.source == key) {
        return result;
      }
    }
    return null;
  }

  Future<void> _startRun() async {
    if (!_canRun) {
      return;
    }
    final outputDir = _timestampedOutputDir(_baseOutputDir!);
    final settings = _currentSettings();

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

    String bibPath;
    if (_useTextMode) {
      bibPath = p.join(outputDir, 'pasted_refs.txt');
      await Directory(outputDir).create(recursive: true);
      await File(bibPath).writeAsString(_textController.text.trim());
    } else {
      bibPath = _bibPath!;
    }

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
      _appendLog('启动校验：${_useTextMode ? "粘贴文本" : p.basename(bibPath)}');
      _appendLog('输出目录：$outputDir');
      final process = await Process.start(
        command.executable,
        args,
        runInShell: false,
        environment: _backendEnvironment(),
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

  Future<void> _testCustomApiSource(int index) async {
    if (_runState == RunState.running || _testingApiKeys) {
      return;
    }
    if (index < 0 || index >= _customApiSources.length) {
      return;
    }

    final entry = _customApiSources[index];
    final sourceKey = _apiSourceKeyForEntry(entry);
    if (sourceKey == null) {
      _appendLog(
          '该卡片还没有可测试的数据源：请填写 Springer/IEEE/CORE 环境变量名，或填写 REST Profile JSON endpoint。');
      return;
    }

    final source =
        entry.toSource().copyWith(enabled: true, searchEnabled: true);
    final settings = RunSettings(
      threshold: _threshold,
      delay: clampDelaySeconds(_delay),
      email: _emailController.text.trim(),
      sources: sourceKey,
      sourceOrder: [sourceKey],
      customApiSources: [source],
      useCrossref: false,
      useOpenAlex: false,
      useSemanticScholar: false,
      useArxiv: false,
      usePubMed: false,
      useDblp: false,
      useUrlVerify: false,
      useSpringer: sourceKey == 'springer',
      useIeee: sourceKey == 'ieee',
      useCore: sourceKey == 'core',
    );

    Directory? tempDir;
    setState(() {
      _testingApiSourceIds.add(entry.id);
      _apiKeyTestResults.removeWhere((item) => item.source == sourceKey);
    });
    _notifyApiKeyTestChanged();

    try {
      tempDir = await Directory.systemTemp.createTemp('refchecker_api_test_');
      final command = await _backendCommand();
      final args = _apiKeyTestArgs(
        settings: settings,
        sourceKey: sourceKey,
        profileDir: tempDir.path,
        scriptPath: command.scriptPath,
      );
      _appendLog(
          '开始测试 ${source.name.isEmpty ? sourceKey : source.name} 连通性（不会在日志中输出 Key 明文）');
      final process = await Process.start(
        command.executable,
        args,
        runInShell: false,
        environment:
            _backendEnvironment(settings: settings, includeApiKeys: true),
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
      if (exitCode != 0) {
        _appendLog('API 连通性测试进程退出码：$exitCode');
      }
    } catch (error) {
      if (!mounted) {
        return;
      }
      _appendLog('API 连通性测试启动失败：$error');
    } finally {
      if (mounted) {
        setState(() {
          _testingApiSourceIds.remove(entry.id);
        });
        _notifyApiKeyTestChanged();
      }
      if (tempDir != null) {
        final dirToDelete = tempDir;
        unawaited(() async {
          try {
            await dirToDelete.delete(recursive: true);
          } catch (_) {}
        }());
      }
    }
  }

  void _notifyApiKeyTestChanged() {
    _apiKeyTestRevision.value += 1;
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
    },
            onError: (Object error) =>
                _appendLog('stderr 解码失败：$error')).asFuture<void>();
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
      final type = asString(decoded['type']);
      switch (type) {
        case 'started':
          setState(() {
            _summary = _summary.copyWith(total: asInt(decoded['total']));
          });
          _appendLog('解析到 ${_summary.total} 条文献');
          break;
        case 'entry_started':
          setState(() {
            _currentKey = asString(decoded['key']);
            _currentTitle = asString(decoded['title']);
          });
          break;
        case 'entry_finished':
          final result = EntryResult.fromJson(decoded);
          setState(() {
            _results.insert(0, result);
          });
          _appendLog(_formatResultLog(result));
          break;
        case 'entry_updated':
          final result = EntryResult.fromJson(decoded);
          setState(() {
            final index = _results.indexWhere((item) => item.key == result.key);
            if (index >= 0) {
              _results[index] = result;
            }
          });
          break;
        case 'summary':
          setState(() {
            _summary = RunSummary.fromJson(decoded);
          });
          _appendLog(
              '校验完成：找到 ${_summary.found}，未找到 ${_summary.notFound}，需人工核查 ${_summary.needsReview}');
          break;
        case 'api_key_test_started':
          _appendLog('API Key 连通性测试已启动');
          break;
        case 'api_key_test_result':
          final payload = decoded['result'];
          if (payload is Map<String, dynamic>) {
            final result = ApiKeyTestResult.fromJson(payload);
            setState(() {
              _apiKeyTestResults
                  .removeWhere((item) => item.source == result.source);
              _apiKeyTestResults.add(result);
            });
            _notifyApiKeyTestChanged();
            _appendLog(_formatApiKeyTestLog(result));
          }
          break;
        case 'api_key_test_summary':
          _notifyApiKeyTestChanged();
          _appendLog(asString(decoded['message']));
          break;
        case 'error':
          if (!_testingApiKeys) {
            setState(() {
              _runState = RunState.failed;
            });
          }
          _appendLog('错误：${asString(decoded['message'])}');
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

  Future<BackendCommand> _backendCommand() async {
    final appDir = File(Platform.resolvedExecutable).parent.path;
    final executableName =
        Platform.isWindows ? 'refchecker_backend.exe' : 'refchecker_backend';
    final candidates = <String>[
      p.join(appDir, executableName),
      p.join(appDir, 'backend', executableName),
      p.join(Directory.current.path, 'backend', executableName),
    ];
    if (Platform.isMacOS) {
      candidates.add(p.normalize(
          p.join(appDir, '..', 'Resources', 'backend', executableName)));
      candidates
          .add(p.normalize(p.join(appDir, '..', 'Resources', executableName)));
    }
    for (final candidate in candidates) {
      if (await File(candidate).exists()) {
        return BackendCommand(executable: candidate);
      }
    }
    final devScript = p.join(Directory.current.path, 'check_bib_crossref.py');
    final bundledScript = p.join(appDir, 'check_bib_crossref.py');
    final scriptPath =
        await File(devScript).exists() ? devScript : bundledScript;
    return BackendCommand(
        executable: _pythonExecutable(), scriptPath: scriptPath);
  }

  Future<BackendCommand> _httpServerCommand() async {
    final appDir = File(Platform.resolvedExecutable).parent.path;
    final executableName = Platform.isWindows
        ? 'refchecker_http_server.exe'
        : 'refchecker_http_server';
    final candidates = <String>[
      p.join(appDir, executableName),
      p.join(appDir, 'backend', executableName),
      p.join(Directory.current.path, 'backend', executableName),
    ];
    if (Platform.isMacOS) {
      candidates.add(p.normalize(
          p.join(appDir, '..', 'Resources', 'backend', executableName)));
      candidates
          .add(p.normalize(p.join(appDir, '..', 'Resources', executableName)));
    }
    for (final candidate in candidates) {
      if (await File(candidate).exists()) {
        return BackendCommand(executable: candidate);
      }
    }
    final devScript = p.join(Directory.current.path, 'refchecker_http_server.py');
    final bundledScript = p.join(appDir, 'refchecker_http_server.py');
    final scriptPath =
        await File(devScript).exists() ? devScript : bundledScript;
    return BackendCommand(
        executable: _pythonExecutable(), scriptPath: scriptPath);
  }

  Future<void> _ensureHttpServerStarted() async {
    if (_httpServerProcess != null) {
      return;
    }
    if (await _isHttpServerHealthy()) {
      _appendLog(
          'Claude 网页版核查服务已在 http://$_httpServerHost:$_httpServerPort 运行');
      return;
    }
    try {
      final command = await _httpServerCommand();
      final args = <String>[
        if (command.scriptPath != null) command.scriptPath!,
        '--host',
        _httpServerHost,
        '--port',
        _httpServerPort.toString(),
      ];
      final settings = _settingsLoaded ? _currentSettings() : null;
      final process = await Process.start(
        command.executable,
        args,
        runInShell: false,
        environment: _backendEnvironment(
          settings: settings,
          includeApiKeys: settings != null,
        ),
      );
      _httpServerProcess = process;
      _appendLog(
          '已自动启动 Claude 网页版核查服务：http://$_httpServerHost:$_httpServerPort');
      unawaited(_listenHttpServerStream(process.stdout));
      unawaited(_listenHttpServerStream(process.stderr));
      unawaited(process.exitCode.then((exitCode) {
        if (_httpServerProcess == process) {
          _httpServerProcess = null;
        }
        if (mounted && exitCode != 0) {
          _appendLog('Claude 网页版核查服务已退出，退出码：$exitCode');
        }
      }));
      await Future<void>.delayed(const Duration(milliseconds: 700));
      if (!await _isHttpServerHealthy()) {
        _appendLog('Claude 网页版核查服务正在启动；浏览器扩展稍后会自动连上');
      }
    } catch (error) {
      _appendLog('Claude 网页版核查服务启动失败：$error');
    }
  }

  Future<bool> _isHttpServerHealthy() async {
    final client = HttpClient()
      ..connectionTimeout = const Duration(milliseconds: 800);
    try {
      final request = await client.getUrl(
        Uri.parse('http://$_httpServerHost:$_httpServerPort/health'),
      );
      final response =
          await request.close().timeout(const Duration(seconds: 1));
      await response.drain<void>();
      return response.statusCode == HttpStatus.ok;
    } catch (_) {
      return false;
    } finally {
      client.close(force: true);
    }
  }

  Future<void> _listenHttpServerStream(Stream<List<int>> stream) {
    return stream
        .transform(const Utf8Decoder(allowMalformed: true))
        .transform(const LineSplitter())
        .listen(
      (line) {
        final trimmed = line.trim();
        if (trimmed.isEmpty || trimmed.contains('GET /health')) {
          return;
        }
        _appendLog('网页核查服务：$trimmed');
      },
      onError: (Object error) => _appendLog('网页核查服务输出解码失败：$error'),
    ).asFuture<void>();
  }

  RunSettings _currentSettings() {
    return RunSettings(
      threshold: _threshold,
      delay: clampDelaySeconds(_delay),
      email: _emailController.text.trim(),
      sources: _visibleSourceOrder().where(_isSourceEnabled).join(','),
      sourceOrder: _completeSourceOrder(),
      customApiSources: _customApiSources.map((e) => e.toSource()).toList(),
      useCrossref: _useCrossref,
      useOpenAlex: _useOpenAlex,
      useSemanticScholar: _useSemanticScholar,
      useArxiv: _useArxiv,
      usePubMed: _usePubMed,
      useDblp: _useDblp,
      useUrlVerify: _useUrlVerify,
      useSpringer: _useSpringer && _customApiSourceEnabled('springer'),
      useIeee: _useIeee && _customApiSourceEnabled('ieee'),
      useCore: _useCore && _customApiSourceEnabled('core'),
    );
  }


  Map<String, String> _backendEnvironment({
    RunSettings? settings,
    bool includeApiKeys = false,
  }) {
    final environment = <String, String>{
      'PYTHONUTF8': '1',
      'PYTHONIOENCODING': 'utf-8',
    };
    if (includeApiKeys && settings != null) {
      for (final src in settings.customApiSources) {
        if (src.enabled && src.apiKey.isNotEmpty && src.envVar.isNotEmpty) {
          environment[src.envVar] = src.apiKey;
        }
      }
    }
    return environment;
  }

  String _pythonExecutable() {
    if (Platform.isWindows) {
      return 'python';
    }
    return 'python3';
  }

  List<Map<String, dynamic>> _customRestProfilesForBackend(
    Iterable<CustomApiSource> sources, {
    bool includeDisabled = false,
    bool forceEnabled = false,
  }) {
    final profiles = <Map<String, dynamic>>[];
    for (final src in sources) {
      if (!includeDisabled && (!src.enabled || !src.searchEnabled)) {
        continue;
      }

      final raw = src.restProfileJson.trim();
      if (raw.isNotEmpty) {
        try {
          final decoded = jsonDecode(raw);
          final profile = _firstRestProfileObject(decoded);
          if (profile == null) {
            continue;
          }
          profile['id'] = src.id;
          if (asString(profile['name']).trim().isEmpty) {
            profile['name'] =
                src.name.trim().isEmpty ? 'Custom REST API' : src.name.trim();
          }
          if (asString(profile['apiKey']).trim().isEmpty &&
              src.apiKey.trim().isNotEmpty) {
            profile['apiKey'] = src.apiKey.trim();
          }
          profile['enabled'] = forceEnabled ? true : src.enabled;
          if (asString(profile['endpoint']).trim().isNotEmpty) {
            profiles.add(profile);
          }
        } catch (_) {
          continue;
        }
        continue;
      }

      if (src.endpoint.trim().isNotEmpty) {
        final profile = Map<String, dynamic>.from(src.toJson());
        profile['id'] = src.id;
        profile['name'] =
            src.name.trim().isEmpty ? 'Custom REST API' : src.name.trim();
        profile['enabled'] = forceEnabled ? true : src.enabled;
        profiles.add(profile);
      }
    }
    return profiles;
  }

  Map<String, dynamic>? _firstRestProfileObject(Object? decoded) {
    if (decoded is Map) {
      return _stringKeyedMap(decoded);
    }
    if (decoded is List) {
      for (final item in decoded) {
        if (item is Map) {
          return _stringKeyedMap(item);
        }
      }
    }
    return null;
  }

  Map<String, dynamic> _stringKeyedMap(Map<dynamic, dynamic> raw) {
    final map = <String, dynamic>{};
    raw.forEach((key, value) {
      map[key.toString()] = value;
    });
    return map;
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
      clampDelaySeconds(settings.delay).toStringAsFixed(2),
      '--app-version',
      appVersion,
    ]);
    if (settings.email.isNotEmpty) {
      args.addAll(['--email', settings.email]);
    }
    final effectiveSources = settings.effectiveSources;
    if (effectiveSources.isNotEmpty) {
      args.addAll(['--sources', effectiveSources]);
    }
    final customRestProfiles =
        _customRestProfilesForBackend(settings.customApiSources);
    if (customRestProfiles.isNotEmpty) {
      final profilesPath = p.join(outputDir, 'custom_rest_profiles.json');
      File(profilesPath).writeAsStringSync(
        const JsonEncoder.withIndent('  ').convert(customRestProfiles),
      );
      args.addAll(['--custom-rest-profiles', profilesPath]);
    }
    if (!settings.useCrossref) {
      args.add('--no-crossref');
    }
    if (!settings.useOpenAlex) {
      args.add('--no-openalex');
    }
    if (!settings.useSemanticScholar) {
      args.add('--no-semantic-scholar');
    }
    if (!settings.useArxiv) {
      args.add('--no-arxiv');
    }
    if (!settings.usePubMed) {
      args.add('--no-pubmed');
    }
    if (!settings.useDblp) {
      args.add('--no-dblp');
    }
    if (!settings.useUrlVerify) {
      args.add('--no-url-verify');
    }
    if (!settings.useSpringer) {
      args.add('--no-springer');
    }
    if (!settings.useIeee) {
      args.add('--no-ieee');
    }
    if (!settings.useCore) {
      args.add('--no-core');
    }
    String? apiKeyForEnv(String envVar) {
      for (final src in settings.customApiSources) {
        if (src.enabled && src.envVar == envVar && src.apiKey.isNotEmpty) {
          return src.apiKey;
        }
      }
      return null;
    }

    final springerKey = apiKeyForEnv('REFCHECKER_SPRINGER_API_KEY');
    if (springerKey != null) {
      args.addAll(['--springer-api-key', springerKey]);
    }
    final ieeeKey = apiKeyForEnv('REFCHECKER_IEEE_API_KEY');
    if (ieeeKey != null) {
      args.addAll(['--ieee-api-key', ieeeKey]);
    }
    final coreKey = apiKeyForEnv('REFCHECKER_CORE_API_KEY');
    if (coreKey != null) {
      args.addAll(['--core-api-key', coreKey]);
    }
    return args;
  }

  List<String> _apiKeyTestArgs({
    required RunSettings settings,
    required String sourceKey,
    required String profileDir,
    String? scriptPath,
  }) {
    final args = <String>[];
    if (scriptPath != null) {
      args.add(scriptPath);
    }
    args.addAll([
      '--test-api-keys',
      '--jsonl-progress',
      '--sources',
      sourceKey,
    ]);

    if (sourceKey.startsWith('custom:')) {
      final customRestProfiles = _customRestProfilesForBackend(
        settings.customApiSources,
        includeDisabled: true,
        forceEnabled: true,
      );
      if (customRestProfiles.isNotEmpty) {
        final profilesPath =
            p.join(profileDir, 'custom_rest_profile_test.json');
        File(profilesPath).writeAsStringSync(
          const JsonEncoder.withIndent('  ').convert(customRestProfiles),
        );
        args.addAll(['--custom-rest-profiles', profilesPath]);
      }
    }

    String? apiKeyForEnv(String envVar) {
      for (final src in settings.customApiSources) {
        if (src.envVar == envVar && src.apiKey.isNotEmpty) {
          return src.apiKey;
        }
      }
      return null;
    }

    final springerKey = apiKeyForEnv('REFCHECKER_SPRINGER_API_KEY');
    if (springerKey != null) {
      args.addAll(['--springer-api-key', springerKey]);
    }
    final ieeeKey = apiKeyForEnv('REFCHECKER_IEEE_API_KEY');
    if (ieeeKey != null) {
      args.addAll(['--ieee-api-key', ieeeKey]);
    }
    final coreKey = apiKeyForEnv('REFCHECKER_CORE_API_KEY');
    if (coreKey != null) {
      args.addAll(['--core-api-key', coreKey]);
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
    final review = result.needsReview ? ' 需人工核查' : '';
    final source = result.source.isEmpty ? '' : ' ${result.source}';
    final reason = result.reason.isEmpty ? '' : ' ${result.reason}';
    return '${result.key}: ${result.status}$source$sim$review$reason';
  }

  String _formatApiKeyTestLog(ApiKeyTestResult result) {
    final prefix =
        result.ok ? '✅' : (result.status == 'not_configured' ? '⚠️' : '❌');
    final http = result.statusCode.isEmpty ? '' : ' HTTP ${result.statusCode}';
    return '$prefix ${result.name}: ${result.message}$http';
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
    final text =
        _fullLog.isEmpty ? _logs.reversed.join('\n') : _fullLog.toString();
    if (text.trim().isEmpty) {
      _appendLog('暂无日志可复制');
      return;
    }
    await Clipboard.setData(ClipboardData(text: text));
    _appendLog('日志已复制到剪贴板');
  }

  Future<String?> _pickFileWithNativeDialog() async {
    if (Platform.isWindows) {
      return _invokeNativeDialog('pickBibFile');
    }
    if (Platform.isMacOS) {
      return _runAppleScript(
        'POSIX path of (choose file with prompt "选择文献文件 (.bib / .docx / .txt)")',
      );
    }
    _appendLog('当前平台暂未内置文件选择器，请使用命令行模式。');
    return null;
  }

  Future<String?> _pickDirectoryWithNativeDialog(
      {String? initialDirectory}) async {
    if (Platform.isMacOS) {
      final defaultLocation = initialDirectory == null ||
              initialDirectory.trim().isEmpty
          ? ''
          : ' default location POSIX file "${_escapeAppleScriptString(initialDirectory)}"';
      return _runAppleScript(
        'POSIX path of (choose folder with prompt "选择结果保存位置"$defaultLocation)',
      );
    }
    if (!Platform.isWindows) {
      _appendLog('当前平台暂未内置目录选择器，请使用命令行模式。');
      return null;
    }
    return _invokeNativeDialog(
      'pickOutputDir',
      <String, Object?>{'initialDirectory': initialDirectory},
    );
  }

  Future<String?> _runAppleScript(String script) async {
    try {
      final result = await Process.run('osascript', ['-e', script]);
      if (result.exitCode != 0) {
        return null;
      }
      final path = asString(result.stdout).trim();
      return path.isEmpty ? null : path;
    } catch (error) {
      _appendLog('macOS 选择器打开失败：$error');
      return null;
    }
  }

  String _escapeAppleScriptString(String value) {
    return value.replaceAll('\\', '\\\\').replaceAll('"', '\\"');
  }

  Future<String?> _invokeNativeDialog(
    String method, [
    Map<String, Object?> arguments = const <String, Object?>{},
  ]) async {
    if (!Platform.isWindows) {
      _appendLog('当前版本的原生选择器仅在 Windows 上启用');
      return null;
    }
    try {
      final result =
          await _nativeDialogs.invokeMethod<String>(method, arguments);
      if (result == null || result.trim().isEmpty) {
        return null;
      }
      return result;
    } on PlatformException catch (error) {
      _appendLog('选择器打开失败：${error.message ?? error.code}');
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            HeaderBar(
              canRun: _canRun,
              runState: _runState,
              onRun: _startRun,
              onOpenFile: _pickBibFile,
            ),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final narrow = constraints.maxWidth < 940;
                  final controlPanel = ControlPanel(
                    bibPath: _bibPath,
                    outputDir: _baseOutputDir,
                    activeOutputDir: _activeOutputDir,
                    runState: _runState,
                    testingApiKeys: _testingApiKeys,
                    apiKeyTestRevision: _apiKeyTestRevision,
                    advancedOpen: _advancedOpen,
                    threshold: _threshold,
                    delay: clampDelaySeconds(_delay),
                    emailController: _emailController,
                    sourceOrder: _visibleSourceOrder(),
                    sourceEnabled: _isSourceEnabled,
                    sourceNames: _sourceNamesForPanel(),
                    onToggleSource: (key, value) =>
                        setState(() => _setSourceEnabled(key, value)),
                    onReorderSources: _onReorderSources,
                    customApiSources: _customApiSources,
                    useTextMode: _useTextMode,
                    textController: _textController,
                    onPickBib: _pickBibFile,
                    onPickOutputDir: _pickOutputDir,
                    onTestCustomApiSource: _testCustomApiSource,
                    isTestingCustomApiSource: _isTestingCustomApiSource,
                    apiKeyTestResultForCustomApiSource:
                        _apiKeyTestResultForCustomApiSource,
                    onAdvancedChanged: (value) =>
                        setState(() => _advancedOpen = value),
                    onThresholdChanged: (value) =>
                        setState(() => _threshold = value),
                    onDelayChanged: (value) =>
                        setState(() => _delay = clampDelaySeconds(value)),
                    onTextModeChanged: (value) =>
                        setState(() => _useTextMode = value),
                    onSelectAllSources: _selectAllSources,
                    onDeselectAllSources: _deselectAllSources,
                    onAddCustomApiSource: _addCustomApiSource,
                    onRemoveCustomApiSource: _removeCustomApiSource,
                    onToggleCustomApiSourceEnabled: _setCustomApiSourceEnabled,
                  );
                  final resultsPanel = ResultsPanel(
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
