int asInt(dynamic value) {
  if (value is int) {
    return value;
  }
  if (value is num) {
    return value.toInt();
  }
  return int.tryParse('$value') ?? 0;
}

double? asDouble(dynamic value) {
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

String asString(dynamic value) {
  if (value == null) {
    return '';
  }
  return '$value';
}

String trimStr(String text, int maxLength) {
  if (text.length <= maxLength) {
    return text;
  }
  return '${text.substring(0, maxLength - 3)}...';
}
