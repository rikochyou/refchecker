import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:refchecker_desktop/main.dart';
import 'package:refchecker_desktop/models.dart';
import 'package:refchecker_desktop/widgets/control_panel.dart';
import 'package:refchecker_desktop/widgets/header_bar.dart';
import 'package:refchecker_desktop/widgets/results_panel.dart';

void main() {
  testWidgets('RefChecker home renders primary workflow', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 900));
    await tester.pumpWidget(const RefCheckerApp());

    expect(find.text('RefChecker'), findsOneWidget);
    expect(find.text('文献文件 (.bib / .docx / .txt)'), findsOneWidget);
    expect(find.text('结果保存位置'), findsOneWidget);
    expect(find.text('开始校验'), findsOneWidget);
    expect(find.text('粘贴文本'), findsOneWidget);
  });

  testWidgets('running header exposes cancel button', (tester) async {
    var cancelled = false;
    await tester.binding.setSurfaceSize(const Size(1280, 180));
    await tester.pumpWidget(
      Directionality(
        textDirection: TextDirection.ltr,
        child: HeaderBar(
          canRun: false,
          runState: RunState.running,
          cancelRequested: false,
          onRun: () {},
          onCancelRun: () => cancelled = true,
          onOpenFile: () {},
        ),
      ),
    );

    expect(find.text('终止任务'), findsOneWidget);
    await tester.tap(find.text('终止任务'));
    expect(cancelled, isTrue);
  });

  testWidgets('LLM API configuration opens card-style dialog', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 900));
    final emailController = TextEditingController();
    final textController = TextEditingController();
    final llmModelController = TextEditingController(text: 'gpt-4o-mini');
    final llmBaseUrlController =
        TextEditingController(text: 'https://api.openai.com/v1');
    final llmApiKeyController = TextEditingController();
    final llmEntry = LlmApiConfigEntry(
      id: 'llm-default',
      nameController: TextEditingController(text: '默认 LLM'),
      providerController: TextEditingController(text: 'openai-compatible'),
      modelController: TextEditingController(text: 'gpt-4o-mini'),
      baseUrlController: TextEditingController(text: 'https://api.openai.com/v1'),
      apiKeyController: TextEditingController(),
      enabled: true,
    );
    final apiKeyTestRevision = ValueNotifier<int>(0);
    final llmApiTestRevision = ValueNotifier<int>(0);
    addTearDown(() {
      emailController.dispose();
      textController.dispose();
      llmModelController.dispose();
      llmBaseUrlController.dispose();
      llmApiKeyController.dispose();
      llmEntry.dispose();
      apiKeyTestRevision.dispose();
      llmApiTestRevision.dispose();
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SizedBox(
            width: 720,
            height: 860,
            child: ControlPanel(
              bibPath: null,
              outputDir: 'C:\\tmp',
              activeOutputDir: null,
              runState: RunState.idle,
              testingApiKeys: false,
              apiKeyTestRevision: apiKeyTestRevision,
              advancedOpen: true,
              threshold: 0.85,
              delay: defaultDelaySeconds,
              emailController: emailController,
              sourceOrder: const ['crossref'],
              sourceEnabled: (_) => true,
              sourceNames: const {'crossref': 'CrossRef'},
              searchMode: 'strict',
              doiCheck: 'auto',
              llmParseMode: 'auto',
              llmModelController: llmModelController,
              llmBaseUrlController: llmBaseUrlController,
              llmApiKeyController: llmApiKeyController,
              llmApiConfigs: [llmEntry],
              selectedLlmApiConfigId: 'llm-default',
              llmApiTestRevision: llmApiTestRevision,
              onToggleSource: (_, __) {},
              onReorderSources: (_, __) {},
              customApiSources: const [],
              useTextMode: false,
              textController: textController,
              onPickBib: () {},
              onPickOutputDir: () {},
              onTestCustomApiSource: (_) {},
              isTestingCustomApiSource: (_) => false,
              apiKeyTestResultForCustomApiSource: (_) => null,
              onAdvancedChanged: (_) {},
              onThresholdChanged: (_) {},
              onDelayChanged: (_) {},
              onTextModeChanged: (_) {},
              onSearchModeChanged: (_) {},
              onDoiCheckChanged: (_) {},
              onLlmParseModeChanged: (_) {},
              onAddLlmApiConfig: () {},
              onRemoveLlmApiConfig: (_) {},
              onSelectLlmApiConfig: (_) {},
              onTestLlmApiConfig: (_) {},
              isTestingLlmApiConfig: (_) => false,
              llmApiTestResultForConfig: (_) => null,
              onSelectAllSources: () {},
              onDeselectAllSources: () {},
              onAddCustomApiSource: () {},
              onRemoveCustomApiSource: (_) {},
              onToggleCustomApiSourceEnabled: (_, __) {},
            ),
          ),
        ),
      ),
    );

    expect(find.text('默认 LLM'), findsOneWidget);
    final configButton = find.widgetWithText(OutlinedButton, '配置 LLM API');
    await tester.ensureVisible(configButton);
    await tester.tap(configButton);
    await tester.pumpAndSettle();

    expect(find.text('配置 LLM API'), findsWidgets);
    expect(find.text('默认 LLM'), findsWidgets);
    await tester.tap(find.byTooltip('编辑配置').first);
    await tester.pumpAndSettle();

    expect(find.text('接口类型 / Provider'), findsOneWidget);
    expect(find.text('LLM API Key'), findsOneWidget);
    expect(find.text('测试连接'), findsOneWidget);
    expect(find.textContaining('沿用数据源 API'), findsOneWidget);
  });

  testWidgets('result detail highlights field comparison first',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 900));
    final item = _sampleResult();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SizedBox(
            width: 900,
            height: 700,
            child: ResultList(results: [item]),
          ),
        ),
      ),
    );

    expect(find.text('\u7ed3\u8bba\u4e0e\u5b57\u6bb5\u5bf9\u6bd4'), findsOneWidget);
    await tester.tap(find.text('ref[1]'));
    await tester.pumpAndSettle();

    expect(find.text('\u5b57\u6bb5\u5bf9\u6bd4'), findsOneWidget);
    expect(find.text('\u89e3\u6790\u8f93\u5165'), findsWidgets);
    expect(find.text('\u67e5\u8be2\u8fd4\u56de'), findsWidgets);
    expect(find.text('打开链接'), findsWidgets);
    expect(find.textContaining('\u8f93\u5165\u53ef\u80fd\u7f3a\u5c11'), findsOneWidget);
  });

}


EntryResult _sampleResult() {
  return const EntryResult(
    key: 'ref[1]',
    title: 'Attention is All You Need',
    status: 'found',
    needsReview: false,
    riskLevel: 'medium',
    confidenceScore: 82,
    suggestedAction: '\u6838\u5bf9\u4f5c\u8005\u987a\u5e8f\u3002',
    source: 'arXiv',
    similarity: 1.0,
    reason: '',
    matchedTitle: 'Attention Is All You Need',
    riskExplanation: '\u4f5c\u8005\u5b57\u6bb5\u5b58\u5728\u5dee\u5f02\uff0c\u5efa\u8bae\u62bd\u67e5\u3002',
    fixSuggestion: '\u6838\u5bf9\u4f5c\u8005\u987a\u5e8f\u548c\u7f3a\u5931\u4f5c\u8005\u3002',
    fixSuggestionBasis: '\u57fa\u4e8e\u4f5c\u8005\u5b57\u6bb5\u5bf9\u6bd4\u3002',
    parser: 'llm',
    parserNote: 'LLM-first parsing; extracted: title, authors',
    parserConfidence: '0.95',
    parserWarning: '',
    llmParseMode: 'auto',
    candidateCount: 1,
    arbitrationReason: 'arXiv hit.',
    sourceTrace: 'arXiv: 100%',
    searchMode: 'strict',
    sourceOrder: 'arxiv,crossref',
    actualQueryTrace: 'arxiv',
    adoptedSource: 'arXiv',
    doiCheckStatus: 'not_provided',
    doiCheckMessage: '',
    doiResolvedUrl: '',
    doiTargetTitle: '',
    doiTargetYear: '',
    doiTargetDoi: '',
    alternativeCandidates: '',
    candidateConflict: '',
    standardCitationAvailable: true,
    standardCitationBasis: 'arXiv metadata',
    standardCitationApa: 'Vaswani, A. (2017). Attention is All You Need.',
    standardCitationBibtex: '@article{vaswani2017attention}',
    standardCitationGbt7714: 'Vaswani A. Attention is All You Need.',
    authorCheck: 'partial',
    authorReason: '\u524d 7 \u4f4d\u4f5c\u8005\u4e00\u81f4\uff0c\u8fd4\u56de\u8bb0\u5f55\u8fd8\u6709 1 \u4f4d\u4f5c\u8005\u3002',
    yearCheck: 'exact',
    yearReason: '\u5e74\u4efd\u4e00\u81f4',
    doiCheck: 'not_provided',
    doiReason: '',
    bibDoi: '',
    matchedDoi: '',
    bibUrl: 'https://arxiv.org/abs/1706.03762',
    matchedUrl: 'https://arxiv.org/abs/1706.03762',
    bibYear: '2017',
    matchedYear: '2017',
    bibAuthors: 'A. Vaswani; N. Shazeer',
    matchedAuthors: 'A. Vaswani; N. Shazeer; I. Polosukhin',
    missingAuthors: 'I. Polosukhin',
    extraAuthors: '',
    bibAuthorCount: 7,
    matchedAuthorCount: 8,
    matchedVenue: 'arXiv',
    matchedType: 'preprint',
  );
}
