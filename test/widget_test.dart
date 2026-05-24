import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:refchecker_desktop/main.dart';

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
}
