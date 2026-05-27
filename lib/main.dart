import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui' show AppExitResponse;

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

class _UpdateBanner extends StatelessWidget {
  const _UpdateBanner({
    required this.info,
    required this.currentVersion,
    required this.onViewRelease,
    required this.onDownload,
    required this.onDismiss,
  });

  final _UpdateInfo info;
  final String currentVersion;
  final VoidCallback onViewRelease;
  final VoidCallback onDownload;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 10, 12, 10),
      decoration: const BoxDecoration(
        color: Color(0xfffffbeb),
        border: Border(bottom: BorderSide(color: Color(0xfff1d08a))),
      ),
      child: Row(
        children: [
          const Icon(Icons.system_update_alt_rounded, color: Color(0xff9a6500)),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '发现新版本 v${info.latestVersion}（当前 v$currentVersion）',
                  style: const TextStyle(
                    color: Color(0xff684600),
                    fontWeight: FontWeight.w800,
                  ),
                ),
                if (info.releaseNotes.isNotEmpty)
                  Text(
                    info.releaseNotes,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Color(0xff7c5a16),
                      fontSize: 12,
                    ),
                  )
                else
                  const Text(
                    '建议下载新版便携包。若本次包含浏览器插件更新，请重新加载插件目录。',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: Color(0xff7c5a16),
                      fontSize: 12,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          TextButton(
            onPressed: onViewRelease,
            child: const Text('查看更新'),
          ),
          const SizedBox(width: 6),
          FilledButton.tonalIcon(
            onPressed: onDownload,
            icon: const Icon(Icons.download_rounded, size: 18),
            label: const Text('下载新版'),
          ),
          IconButton(
            tooltip: '关闭更新提示',
            onPressed: onDismiss,
            icon: const Icon(Icons.close_rounded),
          ),
        ],
      ),
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

class _UpdateInfo {
  const _UpdateInfo({
    required this.latestVersion,
    required this.releaseUrl,
    required this.downloadUrl,
    required this.releaseNotes,
  });

  final String latestVersion;
  final String releaseUrl;
  final String downloadUrl;
  final String releaseNotes;
}

class _ParsedVersion {
  const _ParsedVersion({
    required this.core,
    required this.preRelease,
  });

  final List<int> core;
  final List<String> preRelease;

  static _ParsedVersion parse(String value) {
    var normalized = value.trim().replaceFirst(RegExp(r'^[vV]'), '');
    normalized = normalized.split('+').first;
    final pieces = normalized.split('-');
    final coreParts = pieces.first
        .split('.')
        .map((part) => int.tryParse(part) ?? 0)
        .toList(growable: false);
    final preRelease = pieces.length > 1
        ? pieces.sublist(1).join('-').split('.')
        : const <String>[];
    return _ParsedVersion(core: coreParts, preRelease: preRelease);
  }
}

class _RefCheckerHomePageState extends State<RefCheckerHomePage> {
  static const _nativeDialogs = MethodChannel('refchecker/native_dialogs');
  static const _httpServerHost = '127.0.0.1';
  static const _httpServerPort = 8765;
  static const _githubReleasesApiUrl =
      'https://api.github.com/repos/rikochyou/refchecker/releases?per_page=20';
  static const _githubLatestReleaseUrl =
      'https://github.com/rikochyou/refchecker/releases/latest';

  final _emailController = TextEditingController();
  final _textController = TextEditingController();
  final _llmModelController = TextEditingController(text: 'gpt-4o-mini');
  final _llmBaseUrlController =
      TextEditingController(text: 'https://api.openai.com/v1');
  final _llmApiKeyController = TextEditingController();
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
  String _searchMode = 'strict';
  String _doiCheck = 'auto';
  String _llmParseMode = 'off';
  String _llmProvider = 'openai-compatible';
  String _selectedLlmApiConfigId = '';
  List<String> _sourceOrder = defaultSourceOrder();

  final List<LlmApiConfigEntry> _llmApiConfigs = [];
  final List<CustomApiSourceEntry> _customApiSources = [];
  int _llmConfigIdSeed = 0;
  int _customSourceIdSeed = 0;
  bool _settingsLoaded = false;
  Timer? _saveTimer;
  Timer? _httpRestartTimer;
  bool _checkingForUpdates = false;
  bool _updateDismissed = false;
  _UpdateInfo? _updateInfo;

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
  final List<ApiKeyTestResult> _llmApiTestResults = [];
  final ValueNotifier<int> _apiKeyTestRevision = ValueNotifier<int>(0);
  final ValueNotifier<int> _llmApiTestRevision = ValueNotifier<int>(0);
  final Set<String> _testingApiSourceIds = <String>{};
  final Set<String> _testingLlmApiConfigIds = <String>{};
  final StringBuffer _fullLog = StringBuffer();
  IOSink? _logSink;
  String _logPath = '';
  Process? _process;
  Process? _httpServerProcess;
  Future<void>? _httpServerStartFuture;
  Timer? _httpServerHeartbeatTimer;
  String? _httpServerHeartbeatPath;
  AppLifecycleListener? _appLifecycleListener;
  bool _isAppExiting = false;
  bool _isStoppingChildProcesses = false;
  bool _cancelRequested = false;
  bool get _testingApiKeys => _testingApiSourceIds.isNotEmpty;
  bool get _testingLlmApiKeys => _testingLlmApiConfigIds.isNotEmpty;
  bool get _testingAnyApiKeys => _testingApiKeys || _testingLlmApiKeys;

  bool get _canRun =>
      _runState != RunState.running &&
      !_testingAnyApiKeys &&
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
    _appLifecycleListener = AppLifecycleListener(
      onExitRequested: _handleAppExitRequested,
      onDetach: () {
        unawaited(_shutdownChildProcesses(log: false));
      },
    );
    _emailController.addListener(_scheduleSaveSettings);
    _textController.addListener(_scheduleSaveSettings);
    _llmModelController.addListener(_scheduleSaveSettings);
    _llmBaseUrlController.addListener(_scheduleSaveSettings);
    _llmApiKeyController.addListener(_scheduleSaveSettings);
    _llmModelController.addListener(_scheduleHttpServerRestart);
    _llmBaseUrlController.addListener(_scheduleHttpServerRestart);
    _llmApiKeyController.addListener(_scheduleHttpServerRestart);
    unawaited(_loadSettings().then((_) => _ensureHttpServerStarted()));
    unawaited(_checkForUpdates());
  }

  @override
  void dispose() {
    _appLifecycleListener?.dispose();
    _appLifecycleListener = null;
    _saveTimer?.cancel();
    _httpRestartTimer?.cancel();
    _emailController.dispose();
    _textController.dispose();
    _llmModelController.dispose();
    _llmBaseUrlController.dispose();
    _llmApiKeyController.dispose();
    for (final entry in _customApiSources) {
      entry.dispose();
    }
    for (final entry in _llmApiConfigs) {
      entry.dispose();
    }
    _apiKeyTestRevision.dispose();
    _llmApiTestRevision.dispose();
    unawaited(_logSink?.flush());
    unawaited(_logSink?.close());
    if (!_isAppExiting) {
      unawaited(_shutdownChildProcesses(log: false));
    }
    super.dispose();
  }

  Future<AppExitResponse> _handleAppExitRequested() async {
    _isAppExiting = true;
    try {
      await _shutdownChildProcesses(log: false)
          .timeout(const Duration(seconds: 6));
    } catch (_) {
      // Do not block application exit indefinitely. The HTTP server also
      // monitors this app's PID and will self-terminate if the app disappears.
    }
    return AppExitResponse.exit;
  }

  Future<void> _shutdownChildProcesses({required bool log}) async {
    if (_isStoppingChildProcesses) {
      return;
    }
    _isStoppingChildProcesses = true;
    _httpRestartTimer?.cancel();
    _stopHttpServerHeartbeat(delete: true);
    try {
      final httpProcess = _httpServerProcess;
      _httpServerProcess = null;
      if (httpProcess != null) {
        await _stopHttpServerProcess(httpProcess, log: log);
      }

      final runningProcess = _process;
      _process = null;
      if (runningProcess != null) {
        await _terminateProcessTree(
          runningProcess,
          label: '后端进程',
          log: log,
        );
      }
    } finally {
      _isStoppingChildProcesses = false;
    }
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
        _ensureDefaultLlmApiConfigs();
        _ensureDefaultApiSources();
        _settingsLoaded = true;
        return;
      }
      final json = jsonDecode(await file.readAsString());
      if (json is! Map<String, dynamic>) {
        _ensureDefaultLlmApiConfigs();
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
        _searchMode = settings.searchMode == 'parallel' ? 'parallel' : 'strict';
        _doiCheck = settings.doiCheck == 'off' ? 'off' : 'auto';
        _llmParseMode = switch (settings.llmParseMode) {
          'auto' => 'auto',
          'always' => 'always',
          _ => 'off',
        };
        _llmProvider = settings.llmProvider.isEmpty
            ? 'openai-compatible'
            : settings.llmProvider;
        _llmModelController.text = settings.llmModel;
        _llmBaseUrlController.text = settings.llmBaseUrl;
        _llmApiKeyController.text = settings.llmApiKey;
        _resetLlmApiConfigsFromSettings(settings);
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
        if (_llmApiConfigs.isEmpty) {
          _ensureDefaultLlmApiConfigs();
        }
      });
      _settingsLoaded = true;
    } catch (_) {
      _ensureDefaultLlmApiConfigs();
      _ensureDefaultApiSources();
      _settingsLoaded = true;
    }
  }

  void _resetLlmApiConfigsFromSettings(RunSettings settings) {
    for (final entry in _llmApiConfigs) {
      entry.dispose();
    }
    _llmApiConfigs.clear();

    final configs = settings.llmApiConfigs.isNotEmpty
        ? settings.llmApiConfigs
        : [
            LlmApiConfig(
              id: 'llm-default',
              name: '默认 LLM',
              provider: settings.llmProvider.isEmpty
                  ? 'openai-compatible'
                  : settings.llmProvider,
              model:
                  settings.llmModel.isEmpty ? 'gpt-4o-mini' : settings.llmModel,
              baseUrl: settings.llmBaseUrl.isEmpty
                  ? 'https://api.openai.com/v1'
                  : settings.llmBaseUrl,
              apiKey: settings.llmApiKey,
              enabled: true,
            ),
          ];

    for (var i = 0; i < configs.length; i++) {
      final config = configs[i];
      final entry = _entryFromLlmConfig(
        config.copyWith(
          enabled: config.enabled ||
              (settings.selectedLlmApiConfigId.isEmpty && i == 0),
        ),
      );
      _attachLlmApiConfigListeners(entry);
      _llmApiConfigs.add(entry);
    }

    _selectedLlmApiConfigId = settings.selectedLlmApiConfigId;
    if (_selectedLlmApiConfigId.isEmpty ||
        !_llmApiConfigs.any((entry) => entry.id == _selectedLlmApiConfigId)) {
      LlmApiConfigEntry? selected;
      for (final entry in _llmApiConfigs) {
        if (entry.enabled) {
          selected = entry;
          break;
        }
      }
      selected ??= _llmApiConfigs.isEmpty ? null : _llmApiConfigs.first;
      _selectedLlmApiConfigId = selected?.id ?? '';
    }
    for (final entry in _llmApiConfigs) {
      entry.enabled = entry.id == _selectedLlmApiConfigId;
    }
    _syncActiveLlmControllersFromSelected();
  }

  void _ensureDefaultLlmApiConfigs() {
    if (_llmApiConfigs.isNotEmpty) return;
    final entry = _entryFromLlmConfig(
      LlmApiConfig(
        id: 'llm-default',
        name: '默认 LLM',
        provider: _llmProvider.isEmpty ? 'openai-compatible' : _llmProvider,
        model: _llmModelController.text.trim().isEmpty
            ? 'gpt-4o-mini'
            : _llmModelController.text.trim(),
        baseUrl: _llmBaseUrlController.text.trim().isEmpty
            ? 'https://api.openai.com/v1'
            : _llmBaseUrlController.text.trim(),
        apiKey: _llmApiKeyController.text.trim(),
        enabled: true,
      ),
    );
    _attachLlmApiConfigListeners(entry);
    _llmApiConfigs.add(entry);
    _selectedLlmApiConfigId = entry.id;
    _syncActiveLlmControllersFromSelected();
  }

  LlmApiConfigEntry _entryFromLlmConfig(LlmApiConfig config) {
    final id = config.id.trim().isEmpty ? _newLlmConfigId() : config.id.trim();
    return LlmApiConfigEntry(
      id: id,
      nameController: TextEditingController(
        text: config.name.trim().isEmpty ? '默认 LLM' : config.name.trim(),
      ),
      providerController: TextEditingController(
        text: config.provider.trim().isEmpty
            ? 'openai-compatible'
            : config.provider.trim(),
      ),
      modelController: TextEditingController(
        text: config.model.trim().isEmpty ? 'gpt-4o-mini' : config.model.trim(),
      ),
      baseUrlController: TextEditingController(
        text: config.baseUrl.trim().isEmpty
            ? 'https://api.openai.com/v1'
            : config.baseUrl.trim(),
      ),
      apiKeyController: TextEditingController(text: config.apiKey.trim()),
      enabled: config.enabled,
    );
  }

  String _newLlmConfigId() {
    String id;
    do {
      _llmConfigIdSeed += 1;
      id = 'llm-$_llmConfigIdSeed';
    } while (_llmApiConfigs.any((entry) => entry.id == id));
    return id;
  }

  void _attachLlmApiConfigListeners(LlmApiConfigEntry entry) {
    void listener() {
      _scheduleSaveSettings();
      if (entry.id == _selectedLlmApiConfigId || entry.enabled) {
        _scheduleHttpServerRestart();
      }
      if (mounted) {
        setState(() {});
      }
    }

    entry.nameController.addListener(listener);
    entry.providerController.addListener(listener);
    entry.modelController.addListener(listener);
    entry.baseUrlController.addListener(listener);
    entry.apiKeyController.addListener(listener);
  }

  LlmApiConfigEntry? _selectedLlmApiEntry() {
    for (final entry in _llmApiConfigs) {
      if (entry.id == _selectedLlmApiConfigId) {
        return entry;
      }
    }
    for (final entry in _llmApiConfigs) {
      if (entry.enabled) {
        return entry;
      }
    }
    return _llmApiConfigs.isEmpty ? null : _llmApiConfigs.first;
  }

  void _syncActiveLlmControllersFromSelected() {
    final entry = _selectedLlmApiEntry();
    if (entry == null) return;
    _llmProvider = entry.providerController.text.trim().isEmpty
        ? 'openai-compatible'
        : entry.providerController.text.trim();
    _llmModelController.text = entry.modelController.text.trim();
    _llmBaseUrlController.text = entry.baseUrlController.text.trim();
    _llmApiKeyController.text = entry.apiKeyController.text.trim();
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
      _scheduleHttpServerRestart();
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

  void _scheduleHttpServerRestart() {
    if (_isAppExiting) return;
    if (!_settingsLoaded) return;
    _httpRestartTimer?.cancel();
    _httpRestartTimer = Timer(const Duration(milliseconds: 900), () {
      unawaited(_restartHttpServer());
    });
  }

  Future<void> _restartHttpServer() async {
    if (_isAppExiting) {
      return;
    }
    if (_runState == RunState.running) {
      return;
    }
    await _stopOwnedHttpServer();
    await _ensureHttpServerStarted();
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

  Future<void> _checkForUpdates() async {
    if (_checkingForUpdates) {
      return;
    }
    setState(() {
      _checkingForUpdates = true;
    });

    try {
      final update = await _fetchLatestUpdateInfo();
      if (!mounted) {
        return;
      }
      if (update != null &&
          _compareAppVersions(update.latestVersion, appVersion) > 0) {
        setState(() {
          _updateInfo = update;
          _updateDismissed = false;
        });
      }
    } catch (_) {
      // Network access may be blocked by enterprise/firewall settings. Update
      // checks should never interrupt local reference verification.
    } finally {
      if (mounted) {
        setState(() {
          _checkingForUpdates = false;
        });
      }
    }
  }

  Future<_UpdateInfo?> _fetchLatestUpdateInfo() async {
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 5);
    try {
      final request =
          await client.getUrl(Uri.parse(_githubReleasesApiUrl)).timeout(
                const Duration(seconds: 6),
              );
      request.headers
          .set(HttpHeaders.acceptHeader, 'application/vnd.github+json');
      request.headers
          .set(HttpHeaders.userAgentHeader, 'RefChecker/$appVersion');
      final response =
          await request.close().timeout(const Duration(seconds: 8));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        return null;
      }
      final body = await response.transform(utf8.decoder).join();
      final decoded = jsonDecode(body);
      if (decoded is! List) {
        return null;
      }

      _UpdateInfo? best;
      for (final item in decoded) {
        if (item is! Map) {
          continue;
        }
        if (item['draft'] == true) {
          continue;
        }
        final rawVersion = asString(item['tag_name']).isNotEmpty
            ? asString(item['tag_name'])
            : asString(item['name']);
        final tagVersion = _extractVersion(rawVersion);
        if (tagVersion.isEmpty) {
          continue;
        }
        final releaseUrl = asString(item['html_url']).isEmpty
            ? _githubLatestReleaseUrl
            : asString(item['html_url']);
        final update = _UpdateInfo(
          latestVersion: tagVersion,
          releaseUrl: releaseUrl,
          downloadUrl: _preferredDownloadUrl(item) ?? releaseUrl,
          releaseNotes: trimStr(asString(item['body']).trim(), 180),
        );
        if (best == null ||
            _compareAppVersions(update.latestVersion, best.latestVersion) > 0) {
          best = update;
        }
      }
      return best;
    } finally {
      client.close(force: true);
    }
  }

  String? _preferredDownloadUrl(Map<dynamic, dynamic> release) {
    final assets = release['assets'];
    if (assets is! List) {
      return null;
    }

    String? fallbackZip;
    for (final asset in assets) {
      if (asset is! Map) {
        continue;
      }
      final name = asString(asset['name']).toLowerCase();
      final url = asString(asset['browser_download_url']);
      if (url.isEmpty || !name.endsWith('.zip')) {
        continue;
      }
      fallbackZip ??= url;
      if (name.contains('refchecker') && name.contains('portable')) {
        return url;
      }
    }
    return fallbackZip;
  }

  String _extractVersion(String value) {
    final text = value.trim();
    if (text.isEmpty) {
      return '';
    }
    final match = RegExp(
      r'v?(\d+(?:\.\d+){2}(?:-[A-Za-z0-9][A-Za-z0-9.-]*)?(?:\+[A-Za-z0-9.-]+)?)',
      caseSensitive: false,
    ).firstMatch(text);
    return match?.group(1) ?? text.replaceFirst(RegExp(r'^[vV]'), '');
  }

  int _compareAppVersions(String left, String right) {
    final a = _ParsedVersion.parse(left);
    final b = _ParsedVersion.parse(right);

    final coreLength =
        a.core.length > b.core.length ? a.core.length : b.core.length;
    for (var i = 0; i < coreLength; i++) {
      final diff = (i < a.core.length ? a.core[i] : 0) -
          (i < b.core.length ? b.core[i] : 0);
      if (diff != 0) {
        return diff.sign;
      }
    }

    if (a.preRelease.isEmpty && b.preRelease.isEmpty) {
      return 0;
    }
    if (a.preRelease.isEmpty) {
      return 1;
    }
    if (b.preRelease.isEmpty) {
      return -1;
    }

    final preLength = a.preRelease.length > b.preRelease.length
        ? a.preRelease.length
        : b.preRelease.length;
    for (var i = 0; i < preLength; i++) {
      if (i >= a.preRelease.length) {
        return -1;
      }
      if (i >= b.preRelease.length) {
        return 1;
      }
      final leftPart = a.preRelease[i];
      final rightPart = b.preRelease[i];
      final leftNumber = int.tryParse(leftPart);
      final rightNumber = int.tryParse(rightPart);
      if (leftNumber != null && rightNumber != null) {
        final diff = leftNumber - rightNumber;
        if (diff != 0) {
          return diff.sign;
        }
        continue;
      }
      if (leftNumber != null) {
        return -1;
      }
      if (rightNumber != null) {
        return 1;
      }
      final diff = leftPart.compareTo(rightPart);
      if (diff != 0) {
        return diff.sign;
      }
    }
    return 0;
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

  // ── LLM API configs ──

  void _addLlmApiConfig() {
    final entry = _entryFromLlmConfig(
      LlmApiConfig(
        id: _newLlmConfigId(),
        name: '新的 LLM',
        provider: 'openai-compatible',
        model: 'gpt-4o-mini',
        baseUrl: 'https://api.openai.com/v1',
        apiKey: '',
        enabled: _llmApiConfigs.isEmpty,
      ),
    );
    _attachLlmApiConfigListeners(entry);
    setState(() {
      _llmApiConfigs.add(entry);
      if (_selectedLlmApiConfigId.isEmpty || entry.enabled) {
        _selectLlmApiConfigInMemory(_llmApiConfigs.length - 1);
      }
    });
    _scheduleSaveSettings();
    _scheduleHttpServerRestart();
  }

  void _removeLlmApiConfig(int index) {
    if (index < 0 || index >= _llmApiConfigs.length) return;
    final removingSelected =
        _llmApiConfigs[index].id == _selectedLlmApiConfigId;
    final entry = _llmApiConfigs.removeAt(index);
    _testingLlmApiConfigIds.remove(entry.id);
    _llmApiTestResults.removeWhere((item) => item.source == 'llm:${entry.id}');
    entry.dispose();
    setState(() {
      if (_llmApiConfigs.isEmpty) {
        _selectedLlmApiConfigId = '';
        _ensureDefaultLlmApiConfigs();
      } else if (removingSelected) {
        final newIndex = index >= _llmApiConfigs.length
            ? _llmApiConfigs.length - 1
            : index;
        _selectLlmApiConfigInMemory(newIndex);
      }
    });
    _notifyLlmApiTestChanged();
    _scheduleSaveSettings();
    _scheduleHttpServerRestart();
  }

  void _selectLlmApiConfig(int index) {
    if (index < 0 || index >= _llmApiConfigs.length) return;
    setState(() => _selectLlmApiConfigInMemory(index));
    _scheduleSaveSettings();
    _scheduleHttpServerRestart();
  }

  void _selectLlmApiConfigInMemory(int index) {
    if (index < 0 || index >= _llmApiConfigs.length) return;
    final selected = _llmApiConfigs[index];
    _selectedLlmApiConfigId = selected.id;
    for (final entry in _llmApiConfigs) {
      entry.enabled = entry.id == selected.id;
    }
    _syncActiveLlmControllersFromSelected();
  }

  bool _isTestingLlmApiConfig(int index) {
    if (index < 0) {
      return _testingLlmApiKeys;
    }
    if (index < 0 || index >= _llmApiConfigs.length) {
      return false;
    }
    return _testingLlmApiConfigIds.contains(_llmApiConfigs[index].id);
  }

  ApiKeyTestResult? _llmApiTestResultForConfig(int index) {
    if (index < 0 || index >= _llmApiConfigs.length) {
      return null;
    }
    final source = 'llm:${_llmApiConfigs[index].id}';
    for (final result in _llmApiTestResults.reversed) {
      if (result.source == source) {
        return result;
      }
    }
    return null;
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
      _cancelRequested = false;
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
        environment:
            _backendEnvironment(settings: settings, includeApiKeys: true),
      );
      final stdoutDone = _listenStdout(process.stdout);
      final stderrDone = _listenStderr(process.stderr);
      _process = process;
      if (_cancelRequested) {
        _appendLog('任务已在启动阶段收到终止请求，正在停止后端进程...');
        await _terminateProcessTree(process, label: '后端进程');
      }
      final exitCode = await process.exitCode;
      await Future.wait([stdoutDone, stderrDone]);
      _process = null;
      if (!mounted) {
        return;
      }
      final wasCancelled = _cancelRequested;
      setState(() {
        _runState = !wasCancelled && exitCode == 0
            ? RunState.completed
            : RunState.failed;
        _cancelRequested = false;
      });
      if (wasCancelled) {
        _appendLog('任务已由用户提前终止。');
      } else if (exitCode != 0) {
        _appendLog('后端进程退出码：$exitCode');
      }
      await _finishLogFile();
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _runState = RunState.failed;
        _cancelRequested = false;
      });
      _appendLog('启动失败：$error');
      await _finishLogFile();
    }
  }

  void _cancelRun() {
    if (_runState != RunState.running || _cancelRequested) {
      return;
    }
    setState(() {
      _cancelRequested = true;
    });
    _appendLog('用户请求终止任务，正在停止后端进程...');
    final process = _process;
    if (process == null) {
      _appendLog('后端进程尚未完成启动，将在启动后立即终止。');
      return;
    }
    unawaited(_terminateProcessTree(process, label: '后端进程'));
  }

  Future<void> _terminateProcessTree(
    Process process, {
    required String label,
    bool log = true,
  }) async {
    if (Platform.isWindows) {
      try {
        final result = await Process.run(
          'taskkill',
          ['/PID', process.pid.toString(), '/T', '/F'],
          runInShell: false,
        );
        if (result.exitCode == 0) {
          if (log) {
            _appendLog('$label 进程树已强制终止。');
          }
          return;
        }
        final details = [
          result.stdout.toString().trim(),
          result.stderr.toString().trim(),
        ].where((text) => text.isNotEmpty).join(' ');
        if (log) {
          _appendLog(
            '$label 进程树终止命令返回退出码 ${result.exitCode}'
            '${details.isEmpty ? "" : "：$details"}',
          );
        }
      } catch (error) {
        if (log) {
          _appendLog('$label 进程树终止命令失败：$error');
        }
      }
    }

    try {
      final signaled = process.kill(ProcessSignal.sigterm);
      if (log) {
        _appendLog(signaled ? '$label 已发送终止信号。' : '$label 终止信号发送失败，进程可能已经退出。');
      }
    } catch (error) {
      if (log) {
        _appendLog('$label 终止失败：$error');
      }
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
      searchMode: _searchMode,
      doiCheck: _doiCheck,
      llmParseMode: _llmParseMode,
      llmProvider: _llmProvider,
      llmModel: _llmModelController.text.trim(),
      llmBaseUrl: _llmBaseUrlController.text.trim(),
      llmApiKey: _llmApiKeyController.text.trim(),
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

  Future<void> _testLlmApiConfig(int index) async {
    if (_runState == RunState.running || _testingAnyApiKeys) {
      return;
    }
    if (index < 0 || index >= _llmApiConfigs.length) {
      return;
    }

    final entry = _llmApiConfigs[index];
    final config = entry.toConfig();
    final source = 'llm:${entry.id}';

    setState(() {
      _testingLlmApiConfigIds.add(entry.id);
      _llmApiTestResults.removeWhere((item) => item.source == source);
    });
    _notifyLlmApiTestChanged();
    _appendLog('开始测试 ${_llmConfigDisplayName(config)} 连通性（不会在日志中输出 Key 明文）');

    try {
      final result = await _probeLlmApiConfig(config);
      if (!mounted) {
        return;
      }
      setState(() {
        _llmApiTestResults.removeWhere((item) => item.source == source);
        _llmApiTestResults.add(result);
      });
      _appendLog(_formatApiKeyTestLog(result));
    } catch (error) {
      if (!mounted) {
        return;
      }
      final result = ApiKeyTestResult(
        source: source,
        name: _llmConfigDisplayName(config),
        ok: false,
        status: 'network_error',
        message: 'LLM 连通性测试失败：$error',
        endpoint: _llmChatCompletionsEndpoint(config.baseUrl),
        statusCode: '',
        records: null,
      );
      setState(() {
        _llmApiTestResults.removeWhere((item) => item.source == source);
        _llmApiTestResults.add(result);
      });
      _appendLog(_formatApiKeyTestLog(result));
    } finally {
      if (mounted) {
        setState(() {
          _testingLlmApiConfigIds.remove(entry.id);
        });
        _notifyLlmApiTestChanged();
      }
    }
  }

  Future<ApiKeyTestResult> _probeLlmApiConfig(LlmApiConfig config) async {
    final name = _llmConfigDisplayName(config);
    final endpoint = _llmChatCompletionsEndpoint(config.baseUrl);
    final key = config.apiKey.trim();
    final model = config.model.trim().isEmpty ? 'gpt-4o-mini' : config.model.trim();
    if (key.isEmpty) {
      return ApiKeyTestResult(
        source: 'llm:${config.id}',
        name: name,
        ok: false,
        status: 'not_configured',
        message: '请先填写 LLM API Key。',
        endpoint: endpoint,
        statusCode: '',
        records: null,
      );
    }

    late final Uri uri;
    try {
      uri = Uri.parse(endpoint);
      if (!uri.hasScheme || uri.host.isEmpty) {
        throw const FormatException('缺少协议或主机');
      }
    } catch (error) {
      return ApiKeyTestResult(
        source: 'llm:${config.id}',
        name: name,
        ok: false,
        status: 'invalid_url',
        message: 'Base URL 格式有误：$error',
        endpoint: endpoint,
        statusCode: '',
        records: null,
      );
    }

    final client = HttpClient()..connectionTimeout = const Duration(seconds: 10);
    try {
      final request =
          await client.postUrl(uri).timeout(const Duration(seconds: 12));
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $key');
      request.headers.set(HttpHeaders.contentTypeHeader, 'application/json');
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      request.headers.set(HttpHeaders.userAgentHeader, 'RefChecker/$appVersion');
      request.add(utf8.encode(jsonEncode({
        'model': model,
        'messages': [
          {
            'role': 'user',
            'content': 'ping',
          }
        ],
        'max_tokens': 1,
        'temperature': 0,
      })));
      final response =
          await request.close().timeout(const Duration(seconds: 20));
      final body = await response
          .transform(const Utf8Decoder(allowMalformed: true))
          .join()
          .timeout(const Duration(seconds: 10));
      final ok = response.statusCode >= 200 && response.statusCode < 300;
      return ApiKeyTestResult(
        source: 'llm:${config.id}',
        name: name,
        ok: ok,
        status: ok ? 'ok' : _llmHttpStatus(response.statusCode),
        message: ok
            ? 'LLM 连接成功，模型可响应。'
            : _llmErrorMessage(response.statusCode, body),
        endpoint: endpoint,
        statusCode: response.statusCode.toString(),
        records: null,
      );
    } on TimeoutException {
      return ApiKeyTestResult(
        source: 'llm:${config.id}',
        name: name,
        ok: false,
        status: 'timeout',
        message: '连接超时，请检查 Base URL、网络或服务状态。',
        endpoint: endpoint,
        statusCode: '',
        records: null,
      );
    } finally {
      client.close(force: true);
    }
  }

  String _llmChatCompletionsEndpoint(String baseUrl) {
    var value = baseUrl.trim();
    if (value.isEmpty) {
      value = 'https://api.openai.com/v1';
    }
    while (value.endsWith('/')) {
      value = value.substring(0, value.length - 1);
    }
    final lower = value.toLowerCase();
    if (lower.endsWith('/chat/completions')) {
      return value;
    }
    return '$value/chat/completions';
  }

  String _llmConfigDisplayName(LlmApiConfig config) {
    if (config.name.trim().isNotEmpty) {
      return config.name.trim();
    }
    if (config.model.trim().isNotEmpty) {
      return config.model.trim();
    }
    return 'LLM';
  }

  String _llmHttpStatus(int statusCode) {
    return switch (statusCode) {
      401 || 403 => 'unauthorized',
      404 => 'not_found',
      429 => 'rate_limited',
      >= 500 => 'server_error',
      _ => 'http_error',
    };
  }

  String _llmErrorMessage(int statusCode, String body) {
    final detail = trimStr(body.replaceAll(RegExp(r'\\s+'), ' ').trim(), 160);
    final suffix = detail.isEmpty ? '' : '：$detail';
    return switch (statusCode) {
      401 || 403 => '认证失败，请检查 API Key 或服务权限$suffix',
      404 => '接口不存在，请检查 Base URL 是否应以 /v1 结尾，或模型名称是否正确$suffix',
      429 => '请求被限流，请稍后再试$suffix',
      >= 500 => 'LLM 服务返回服务器错误$suffix',
      _ => 'LLM 服务返回 HTTP $statusCode$suffix',
    };
  }

  void _notifyApiKeyTestChanged() {
    _apiKeyTestRevision.value += 1;
  }

  void _notifyLlmApiTestChanged() {
    _llmApiTestRevision.value += 1;
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
    final buildSourceRoot =
        p.normalize(p.join(appDir, '..', '..', '..', '..', '..'));
    final candidates = <String>[
      p.join(appDir, executableName),
      p.join(appDir, 'backend', executableName),
      p.join(Directory.current.path, 'backend', executableName),
      p.join(buildSourceRoot, 'backend', executableName),
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
    final scriptCandidates = <String>[
      p.join(Directory.current.path, 'check_bib_crossref.py'),
      p.join(appDir, 'check_bib_crossref.py'),
      p.join(buildSourceRoot, 'check_bib_crossref.py'),
    ];
    for (final scriptPath in scriptCandidates) {
      if (await File(scriptPath).exists()) {
        return BackendCommand(
            executable: _pythonExecutable(), scriptPath: scriptPath);
      }
    }
    throw StateError(
      '未找到 RefChecker 后端程序。请确认 backend/$executableName 已随应用打包，'
      '或从项目根目录运行。已检查：${candidates.join("；")}；'
      '脚本候选：${scriptCandidates.join("；")}',
    );
  }

  Future<BackendCommand> _httpServerCommand() async {
    final appDir = File(Platform.resolvedExecutable).parent.path;
    final executableName = Platform.isWindows
        ? 'refchecker_http_server.exe'
        : 'refchecker_http_server';
    final buildSourceRoot =
        p.normalize(p.join(appDir, '..', '..', '..', '..', '..'));
    final candidates = <String>[
      p.join(appDir, executableName),
      p.join(appDir, 'backend', executableName),
      p.join(Directory.current.path, 'backend', executableName),
      p.join(buildSourceRoot, 'backend', executableName),
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
    final scriptCandidates = <String>[
      p.join(Directory.current.path, 'refchecker_http_server.py'),
      p.join(appDir, 'refchecker_http_server.py'),
      p.join(buildSourceRoot, 'refchecker_http_server.py'),
    ];
    for (final scriptPath in scriptCandidates) {
      if (await File(scriptPath).exists()) {
        return BackendCommand(
            executable: _pythonExecutable(), scriptPath: scriptPath);
      }
    }
    throw StateError(
      '未找到 RefChecker 网页核查服务。请确认 backend/$executableName 已随应用打包，'
      '或从项目根目录运行。已检查：${candidates.join("；")}；'
      '脚本候选：${scriptCandidates.join("；")}',
    );
  }

  Future<void> _ensureHttpServerStarted() async {
    if (_isAppExiting) {
      return;
    }
    final existingStart = _httpServerStartFuture;
    if (existingStart != null) {
      await existingStart;
      return;
    }
    final startFuture = _ensureHttpServerStartedInternal();
    _httpServerStartFuture = startFuture;
    try {
      await startFuture;
    } finally {
      if (_httpServerStartFuture == startFuture) {
        _httpServerStartFuture = null;
      }
    }
  }

  Future<void> _ensureHttpServerStartedInternal() async {
    if (_isAppExiting) {
      return;
    }
    if (_httpServerProcess != null) {
      return;
    }
    if (await _isHttpServerHealthy()) {
      _appendLog('检测到已有网页核查服务，正在重启以应用当前设置...');
      await _requestHttpServerShutdown();
      await _waitForHttpServerStopped();
      if (await _isHttpServerHealthy()) {
        _appendLog('端口 http://$_httpServerHost:$_httpServerPort 仍被占用，将复用现有服务。');
        return;
      }
    }
    try {
      final command = await _httpServerCommand();
      final heartbeatPath = _httpServerHeartbeatFilePath();
      _writeHttpServerHeartbeat(heartbeatPath);
      final args = <String>[
        if (command.scriptPath != null) command.scriptPath!,
        '--host',
        _httpServerHost,
        '--port',
        _httpServerPort.toString(),
        '--parent-pid',
        pid.toString(),
        '--parent-heartbeat',
        heartbeatPath,
      ];
      final settings = _settingsLoaded ? _currentSettings() : null;
      if (settings != null) {
        args.addAll([
          '--search-mode',
          settings.searchMode,
          '--doi-check',
          settings.doiCheck,
          '--llm-parse-mode',
          settings.llmParseMode,
          '--llm-provider',
          settings.llmProvider,
          '--llm-model',
          settings.llmModel,
          '--llm-base-url',
          settings.llmBaseUrl,
        ]);
        final customRestProfiles =
            _customRestProfilesForBackend(settings.customApiSources);
        if (customRestProfiles.isNotEmpty) {
          final profilesPath = p.join(
            Directory.systemTemp.path,
            'refchecker_http_custom_rest_profiles_$pid.json',
          );
          File(profilesPath).writeAsStringSync(
            const JsonEncoder.withIndent('  ').convert(customRestProfiles),
          );
          args.addAll(['--custom-rest-profiles', profilesPath]);
        }
      }
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
      _startHttpServerHeartbeat(heartbeatPath);
      _appendLog('网页核查服务已启动：http://$_httpServerHost:$_httpServerPort');
      unawaited(_listenHttpServerStream(process.stdout));
      unawaited(_listenHttpServerStream(process.stderr));
      unawaited(process.exitCode.then((exitCode) {
        if (_httpServerProcess == process) {
          _httpServerProcess = null;
          _stopHttpServerHeartbeat(delete: true);
        }
        if (mounted && exitCode != 0) {
          _appendLog('网页核查服务退出码：$exitCode');
        }
      }));
      await Future<void>.delayed(const Duration(milliseconds: 700));
      if (!await _isHttpServerHealthy()) {
        _appendLog('网页核查服务启动后未通过健康检查。');
      }
    } catch (error) {
      _appendLog('网页核查服务启动失败：$error');
    }
  }

  Future<void> _stopOwnedHttpServer() async {
    final process = _httpServerProcess;
    _httpServerProcess = null;
    _stopHttpServerHeartbeat(delete: true);
    if (process == null) {
      return;
    }
    await _stopHttpServerProcess(process, log: false);
  }

  Future<void> _stopHttpServerProcess(
    Process process, {
    required bool log,
  }) async {
    _stopHttpServerHeartbeat(delete: true);
    await _requestHttpServerShutdown();
    try {
      await process.exitCode.timeout(const Duration(seconds: 2));
      return;
    } catch (_) {
      await _terminateProcessTree(process, label: '网页核查服务', log: log);
    }
    try {
      await process.exitCode.timeout(const Duration(seconds: 2));
    } catch (_) {
      try {
        process.kill(ProcessSignal.sigkill);
      } catch (_) {}
    }
  }

  String _httpServerHeartbeatFilePath() {
    return p.join(
      Directory.systemTemp.path,
      'refchecker_http_parent_${pid}_heartbeat.txt',
    );
  }

  void _writeHttpServerHeartbeat(String path) {
    try {
      final file = File(path);
      file.parent.createSync(recursive: true);
      file.writeAsStringSync(DateTime.now().toUtc().toIso8601String());
    } catch (_) {
      // Heartbeat is a cleanup aid. Do not block normal app usage if writing
      // temp files fails; PID monitoring and explicit shutdown remain active.
    }
  }

  void _startHttpServerHeartbeat(String path) {
    _stopHttpServerHeartbeat(delete: true);
    _httpServerHeartbeatPath = path;
    _writeHttpServerHeartbeat(path);
    _httpServerHeartbeatTimer = Timer.periodic(
      const Duration(seconds: 1),
      (_) => _writeHttpServerHeartbeat(path),
    );
  }

  void _stopHttpServerHeartbeat({required bool delete}) {
    _httpServerHeartbeatTimer?.cancel();
    _httpServerHeartbeatTimer = null;
    final path = _httpServerHeartbeatPath;
    _httpServerHeartbeatPath = null;
    if (delete && path != null) {
      try {
        final file = File(path);
        if (file.existsSync()) {
          file.deleteSync();
        }
      } catch (_) {}
    }
  }

  Future<void> _requestHttpServerShutdown() async {
    final client = HttpClient()
      ..connectionTimeout = const Duration(milliseconds: 800);
    try {
      final request = await client
          .postUrl(
              Uri.parse('http://$_httpServerHost:$_httpServerPort/shutdown'))
          .timeout(const Duration(seconds: 1));
      final response =
          await request.close().timeout(const Duration(seconds: 1));
      await response.drain<void>();
    } catch (_) {
      // Older orphaned services may not support /shutdown; avoid starting a
      // duplicate on the same port and simply reuse the existing service.
    } finally {
      client.close(force: true);
    }
  }

  Future<void> _waitForHttpServerStopped() async {
    for (var i = 0; i < 12; i++) {
      await Future<void>.delayed(const Duration(milliseconds: 250));
      if (!await _isHttpServerHealthy()) {
        return;
      }
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
    final activeLlm = _selectedLlmApiEntry()?.toConfig();
    final llmProvider = activeLlm == null
        ? (_llmProvider.isEmpty ? 'openai-compatible' : _llmProvider)
        : (activeLlm.provider.trim().isEmpty
            ? 'openai-compatible'
            : activeLlm.provider.trim());
    final llmModel = activeLlm == null
        ? _llmModelController.text.trim()
        : activeLlm.model.trim();
    final llmBaseUrl = activeLlm == null
        ? _llmBaseUrlController.text.trim()
        : activeLlm.baseUrl.trim();
    final llmApiKey = activeLlm == null
        ? _llmApiKeyController.text.trim()
        : activeLlm.apiKey.trim();
    final selectedLlmId = activeLlm?.id ?? _selectedLlmApiConfigId;
    return RunSettings(
      threshold: _threshold,
      delay: clampDelaySeconds(_delay),
      email: _emailController.text.trim(),
      sources: _visibleSourceOrder().where(_isSourceEnabled).join(','),
      sourceOrder: _completeSourceOrder(),
      searchMode: _searchMode,
      doiCheck: _doiCheck,
      llmParseMode: _llmParseMode,
      llmProvider: llmProvider,
      llmModel: llmModel,
      llmBaseUrl: llmBaseUrl,
      llmApiKey: llmApiKey,
      llmApiConfigs: _llmApiConfigs
          .map((entry) => entry.toConfig().copyWith(
                enabled: entry.id == selectedLlmId,
              ))
          .toList(),
      selectedLlmApiConfigId: selectedLlmId,
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
      'REFCHECKER_APP_VERSION': appVersion,
    };
    if (includeApiKeys && settings != null) {
      for (final src in settings.customApiSources) {
        if (src.enabled && src.apiKey.isNotEmpty && src.envVar.isNotEmpty) {
          environment[src.envVar] = src.apiKey;
        }
      }
      if (settings.llmApiKey.isNotEmpty) {
        environment['REFCHECKER_LLM_API_KEY'] = settings.llmApiKey;
      }
      if (settings.llmModel.isNotEmpty) {
        environment['REFCHECKER_LLM_MODEL'] = settings.llmModel;
      }
      if (settings.llmBaseUrl.isNotEmpty) {
        environment['REFCHECKER_LLM_BASE_URL'] = settings.llmBaseUrl;
      }
      if (settings.llmProvider.isNotEmpty) {
        environment['REFCHECKER_LLM_PROVIDER'] = settings.llmProvider;
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
      '--search-mode',
      settings.searchMode,
      '--doi-check',
      settings.doiCheck,
      '--llm-parse-mode',
      settings.llmParseMode,
      '--llm-provider',
      settings.llmProvider,
      '--llm-model',
      settings.llmModel,
      '--llm-base-url',
      settings.llmBaseUrl,
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
    final updateInfo = _updateDismissed ? null : _updateInfo;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            HeaderBar(
              canRun: _canRun,
              runState: _runState,
              cancelRequested: _cancelRequested,
              onRun: _startRun,
              onCancelRun: _cancelRun,
              onOpenFile: _pickBibFile,
            ),
            if (updateInfo != null)
              _UpdateBanner(
                info: updateInfo,
                currentVersion: appVersion,
                onViewRelease: () => _openPath(updateInfo.releaseUrl),
                onDownload: () => _openPath(updateInfo.downloadUrl),
                onDismiss: () => setState(() => _updateDismissed = true),
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
                    testingApiKeys: _testingAnyApiKeys,
                    apiKeyTestRevision: _apiKeyTestRevision,
                    advancedOpen: _advancedOpen,
                    threshold: _threshold,
                    delay: clampDelaySeconds(_delay),
                    emailController: _emailController,
                    sourceOrder: _visibleSourceOrder(),
                    sourceEnabled: _isSourceEnabled,
                    sourceNames: _sourceNamesForPanel(),
                    searchMode: _searchMode,
                    doiCheck: _doiCheck,
                    llmParseMode: _llmParseMode,
                    llmModelController: _llmModelController,
                    llmBaseUrlController: _llmBaseUrlController,
                    llmApiKeyController: _llmApiKeyController,
                    llmApiConfigs: _llmApiConfigs,
                    selectedLlmApiConfigId: _selectedLlmApiConfigId,
                    llmApiTestRevision: _llmApiTestRevision,
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
                    onSearchModeChanged: (value) {
                      setState(() => _searchMode =
                          value == 'parallel' ? 'parallel' : 'strict');
                      _scheduleSaveSettings();
                    },
                    onDoiCheckChanged: (value) {
                      setState(
                          () => _doiCheck = value == 'off' ? 'off' : 'auto');
                      _scheduleSaveSettings();
                    },
                    onLlmParseModeChanged: (value) {
                      setState(() => _llmParseMode = switch (value) {
                            'auto' => 'auto',
                            'always' => 'always',
                            _ => 'off',
                          });
                      _scheduleSaveSettings();
                      _scheduleHttpServerRestart();
                    },
                    onAddLlmApiConfig: _addLlmApiConfig,
                    onRemoveLlmApiConfig: _removeLlmApiConfig,
                    onSelectLlmApiConfig: _selectLlmApiConfig,
                    onTestLlmApiConfig: _testLlmApiConfig,
                    isTestingLlmApiConfig: _isTestingLlmApiConfig,
                    llmApiTestResultForConfig: _llmApiTestResultForConfig,
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
