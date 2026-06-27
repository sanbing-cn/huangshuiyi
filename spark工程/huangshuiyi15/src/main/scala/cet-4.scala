import scala.io.Source
import scala.collection.mutable
import scala.collection.mutable.ListBuffer
import java.io.{File, PrintWriter}

object CET4Analysis {

  case class Word(
                   word: String,
                   translations: List[(String, String)],
                   posSet: Set[String],
                   phraseCount: Int
                 )

  def main(args: Array[String]): Unit = {
    println("=" * 80)
    println("            CET-4 四级词汇数据分析系统")
    println("=" * 80)

    val basePath = "english-vocabulary-master/json_original/"

    val simpleFiles = List(
      basePath + "json-simple/CET4_1.json",
      basePath + "json-simple/CET4_2.json",
      basePath + "json-simple/CET4_3.json"
    )
    val fullFiles = List(
      basePath + "json-full/CET4_1.json",
      basePath + "json-full/CET4_2.json",
      basePath + "json-full/CET4_3.json"
    )
    val sentenceFiles = List(
      basePath + "json-sentence/CET4_1.json",
      basePath + "json-sentence/CET4_2.json",
      basePath + "json-sentence/CET4_3.json"
    )

    println("\n[1] 读取3种不同格式的CET-4文件")
    println("-" * 60)

    val simpleWords = loadWords(simpleFiles, "json-simple")
    println(s"  json-simple 格式加载: ${simpleWords.size} 个单词")

    val fullWords = loadWords(fullFiles, "json-full")
    println(s"  json-full 格式加载: ${fullWords.size} 个单词")

    val sentenceWords = loadWords(sentenceFiles, "json-sentence")
    println(s"  json-sentence 格式加载: ${sentenceWords.size} 个单词")

    val allWords = (simpleWords ++ fullWords ++ sentenceWords)
      .groupBy(_.word.toLowerCase)
      .map { case (_, words) => words.head }
      .toList
      .sortBy(_.word.toLowerCase)

    println(s"\n  去重后总计: ${allWords.size} 个独立单词")

    println("\n" + "=" * 80)
    println("[2] 按词性分类统计")
    println("=" * 80)
    posAnalysis(allWords)

    println("\n" + "=" * 80)
    println("[3] 单词长度分析")
    println("=" * 80)
    lengthAnalysis(allWords)

    println("\n" + "=" * 80)
    println("[4] A-Z开头单词统计")
    println("=" * 80)
    letterAnalysis(allWords)

    println("\n" + "=" * 80)
    println("[5] 背单词学习计划 & 难度分类")
    println("=" * 80)
    val wordsWithDifficulty = allWords.map { w =>
      val (level, score) = classifyDifficulty(w)
      (w, level, score)
    }
    studyPlan(wordsWithDifficulty)

    println("\n" + "=" * 80)
    println("[6] 导出CSV文件")
    println("=" * 80)
    exportCSV(wordsWithDifficulty)
  }

  // ==================== 2. 词性分析 ====================

  def posAnalysis(words: List[Word]): Unit = {
    val posMap = Map(
      "n" -> "名词",
      "v" -> "动词",
      "adj" -> "形容词",
      "adv" -> "副词"
    )

    val posCounts = mutable.Map[String, Int]().withDefaultValue(0)
    var noPosCount = 0

    words.foreach { w =>
      val normalizedPoses = w.posSet.flatMap(normalizePos)
      if (normalizedPoses.isEmpty) noPosCount += 1
      normalizedPoses.foreach(pos => posCounts(pos) += 1)
    }

    val total = words.size
    println(f"\n${"词性"}%-10s ${"英文标记"}%-10s ${"数量"}%8s ${"占比"}%10s")
    println("-" * 50)

    var maxPos = ""
    var maxCount = 0

    posMap.foreach { case (eng, chn) =>
      val count = posCounts.getOrElse(eng, 0)
      val pct = count.toDouble / total * 100
      println(f"$chn%-10s $eng%-10s $count%8d $pct%9.2f%%")
      if (count > maxCount) {
        maxCount = count
        maxPos = chn
      }
    }

    println(f"${"其他/未知"}%-10s ${"?"}%-10s $noPosCount%8d ${noPosCount.toDouble / total * 100}%9.2f%%")
    println(f"\n  >>> 占比最高的词性: $maxPos ($maxCount 个, 占${maxCount.toDouble / total * 100}%.2f%%)")
  }

  def normalizePos(pos: String): Option[String] = {
    val p = pos.trim.toLowerCase.replaceAll("\\s", "")
    p match {
      case s if s.startsWith("n") || s == "n" => Some("n")
      case s if s.startsWith("v") || s == "v" => Some("v")
      case s if s.startsWith("adj") => Some("adj")
      case s if s.startsWith("adv") => Some("adv")
      case _ => None
    }
  }

  // ==================== 3. 长度分析 ====================

  def lengthAnalysis(words: List[Word]): Unit = {
    val lengths = words.map(_.word.length)
    val avgLen = lengths.sum.toDouble / lengths.size
    val maxLen = lengths.max
    val minLen = lengths.min

    val longestWords = words.filter(_.word.length == maxLen).take(10)
    val shortestWords = words.filter(_.word.length == minLen).take(10)

    println(f"\n  平均单词长度: $avgLen%.2f 个字母")
    println(f"  最长单词: $maxLen 个字母")
    println(s"  最短单词: $minLen 个字母")

    println(s"\n  最长单词示例 (最多10个):")
    longestWords.foreach(w => println(s"    ${w.word} (${w.word.length}字母) - ${firstTranslation(w)}"))

    println(s"\n  最短单词示例 (最多10个):")
    shortestWords.foreach(w => println(s"    ${w.word} (${w.word.length}字母) - ${firstTranslation(w)}"))

    println(s"\n  字母长度分布 (2-15):")
    println(f"  ${"长度"}%-6s ${"数量"}%8s ${"占比"}%10s ${"分布"}%s")
    println("  " + "-" * 65)

    val total = words.size
    (2 to 15).foreach { len =>
      val count = words.count(_.word.length == len)
      val pct = count.toDouble / total * 100
      val barLen = (count.toDouble / total * 200).toInt
      val bar = "█" * barLen
      println(f"  $len%-6d $count%8d $pct%9.2f%%  $bar")
    }

    val otherCount = words.count(w => w.word.length < 2 || w.word.length > 15)
    if (otherCount > 0) {
      println(f"  其他    $otherCount%8d ${otherCount.toDouble / total * 100}%9.2f%%")
    }
  }

  // ==================== 4. 首字母分析 ====================

  def letterAnalysis(words: List[Word]): Unit = {
    println(f"\n${"字母"}%-6s ${"数量"}%8s ${"占比"}%10s ${"分布"}%s")
    println("-" * 70)

    val total = words.size
    val letterCounts = ('A' to 'Z').map { letter =>
      val count = words.count(_.word.toUpperCase.startsWith(letter.toString))
      (letter, count)
    }

    val maxCount = letterCounts.map(_._2).max

    letterCounts.foreach { case (letter, count) =>
      val pct = count.toDouble / total * 100
      val barLen = if (maxCount > 0) (count.toDouble / maxCount * 30).toInt else 0
      val bar = "█" * barLen
      println(f"  $letter%-4s $count%8d $pct%9.2f%%  $bar")
    }

    val (maxLetter, maxC) = letterCounts.maxBy(_._2)
    val (minLetter, minC) = letterCounts.filter(_._2 > 0).minBy(_._2)
    println(s"\n  >>> 数量最多: 字母 $maxLetter ($maxC 个)")
    println(s"  >>> 数量最少: 字母 $minLetter ($minC 个)")
  }

  // ==================== 5. 难度分类与学习计划 ====================

  def classifyDifficulty(word: Word): (String, Int) = {
    val w = word.word.toLowerCase
    var score = 0

    val len = w.length
    if (len <= 3) score += 1
    else if (len <= 5) score += 2
    else if (len <= 7) score += 3
    else if (len <= 10) score += 4
    else if (len <= 13) score += 5
    else score += 6

    val primaryPos = word.posSet.headOption.getOrElse("")
    primaryPos.toLowerCase match {
      case p if p.startsWith("n") && !p.contains("v") => score += 1
      case p if p.startsWith("v") => score += 2
      case p if p.startsWith("adj") => score += 2
      case p if p.startsWith("adv") => score += 3
      case _ => score += 2
    }

    if (word.posSet.size > 2) score += 1

    val prefixes = List("un", "re", "pre", "dis", "mis", "over", "under", "out", "sub", "inter", "trans", "counter")
    val suffixes = List("tion", "sion", "ment", "ness", "ity", "ence", "ance", "ism", "ist", "ology", "graphy", "able", "ible", "ive", "ous", "ious")

    val hasPrefix = prefixes.exists(w.startsWith)
    val hasSuffix = suffixes.exists(w.endsWith)
    if (hasPrefix) score += 1
    if (hasSuffix) score += 1

    val level = if (score <= 3) "简单" else if (score <= 6) "中等" else if (score <= 9) "困难" else "极难"
    (level, score)
  }

  def studyPlan(wordsWithDifficulty: List[(Word, String, Int)]): Unit = {
    val totalWords = wordsWithDifficulty.size
    val days = 30
    val wordsPerDay = math.ceil(totalWords.toDouble / days).toInt

    println(s"\n  === 背单词学习计划 ===")
    println(s"  总单词数: $totalWords")
    println(s"  计划天数: $days 天")
    println(s"  每天新学: $wordsPerDay 个单词")
    println(s"  复习策略: 艾宾浩斯遗忘曲线 (第1/2/4/7/15天复习)")

    println(s"\n  === 每日安排建议 ===")
    println(s"  早上: 新学 ${wordsPerDay} 个单词 (记忆新词)")
    println(s"  中午: 复习昨天学过的单词")
    println(s"  晚上: 复习本周内需要巩固的单词")

    val difficultyStats = wordsWithDifficulty.groupBy(_._2).map { case (level, list) =>
      (level, list.size, list.map(_._1.word.length).sum.toDouble / list.size)
    }.toList.sortBy { t =>
      t._1 match {
        case "简单" => 1
        case "中等" => 2
        case "困难" => 3
        case "极难" => 4
        case _ => 5
      }
    }

    println(s"\n  === 难度分布 ===")
    println(f"  ${"难度"}%-8s ${"数量"}%8s ${"占比"}%10s ${"平均长度"}%10s")
    println("  " + "-" * 50)
    difficultyStats.foreach { case (level, count, avgLen) =>
      val pct = count.toDouble / totalWords * 100
      println(f"  $level%-8s $count%8d $pct%9.2f%% $avgLen%9.2f")
    }

    val sorted = wordsWithDifficulty.sortBy(_._3)
    val dayPlan = sorted.grouped(wordsPerDay).toList

    println(s"\n  === 30天学习计划概览 ===")
    println(f"  ${"天数"}%-6s ${"新学"}%8s ${"累计"}%8s ${"难度范围"}%-16s ${"示例单词"}%s")
    println("  " + "-" * 75)

    dayPlan.zipWithIndex.foreach { case (dayWords, idx) =>
      val day = idx + 1
      val cumulative = math.min((idx + 1) * wordsPerDay, totalWords)
      val scores = dayWords.map(_._3)
      val minScore = scores.min
      val maxScore = scores.max
      val minLevel = scoreToLevel(minScore)
      val maxLevel = scoreToLevel(maxScore)
      val examples = dayWords.take(5).map(_._1.word).mkString(", ")
      println(f"  Day$day%-3d ${dayWords.size}%8d $cumulative%8d $minLevel~$maxLevel%-16s $examples")
    }
  }

  def scoreToLevel(score: Int): String = {
    if (score <= 3) "简单" else if (score <= 6) "中等" else if (score <= 9) "困难" else "极难"
  }

  // ==================== 6. CSV导出 ====================

  def exportCSV(wordsWithDifficulty: List[(Word, String, Int)]): Unit = {
    val outputPath = "CET4_学习计划.csv"
    val writer = new PrintWriter(new File(outputPath))

    writer.print('\ufeff')
    val header = "序号,单词,中文释义,词性,难度等级,难度分数,单词长度,首字母,含前缀,含后缀,学习日,学习建议"
    writer.println(header)

    val sorted = wordsWithDifficulty.sortBy(_._3)
    val wordsPerDay = math.ceil(sorted.size.toDouble / 30).toInt

    sorted.zipWithIndex.foreach { case ((word, level, score), idx) =>
      val day = idx / wordsPerDay + 1
      val translation = firstTranslation(word).replace(",", "，")
      val pos = word.posSet.map(posToLabel).mkString("/")
      val hasPrefixStr = if (hasCommonPrefix(word.word)) "是" else "否"
      val hasSuffixStr = if (hasCommonSuffix(word.word)) "是" else "否"
      val tip = level match {
        case "简单" => "基础词汇，快速记忆"
        case "中等" => "核心词汇，重点掌握"
        case "困难" => "进阶词汇，结合例句记忆"
        case "极难" => "高难词汇，词根词缀拆解记忆"
      }

      writer.println(s"${idx + 1},${word.word},$translation,$pos,$level,$score,${word.word.length},${word.word.head.toUpper},$hasPrefixStr,$hasSuffixStr,Day$day,$tip")
    }

    writer.close()
    println(s"\n  CSV文件已导出: $outputPath")
    println(s"  共 ${sorted.size} 条记录")
  }

  def posToLabel(pos: String): String = {
    val p = pos.trim.toLowerCase
    if (p.startsWith("n")) "名词"
    else if (p.startsWith("v")) "动词"
    else if (p.startsWith("adj")) "形容词"
    else if (p.startsWith("adv")) "副词"
    else pos
  }

  def hasCommonPrefix(word: String): Boolean = {
    val w = word.toLowerCase
    List("un", "re", "pre", "dis", "mis", "over", "under", "out", "sub", "inter", "trans", "counter", "in", "ex", "ab", "de", "com", "con", "pro").exists(w.startsWith)
  }

  def hasCommonSuffix(word: String): Boolean = {
    val w = word.toLowerCase
    List("tion", "sion", "ment", "ness", "ity", "ence", "ance", "ism", "ist", "ology", "graphy", "able", "ible", "ive", "ous", "ious", "ly", "er", "or", "al", "ful", "less", "ize", "ise").exists(w.endsWith)
  }

  def firstTranslation(w: Word): String = {
    w.translations.headOption.map(_._1).getOrElse("")
  }

  // ==================== 数据加载 ====================

  def loadWords(files: List[String], format: String): List[Word] = {
    files.flatMap { file =>
      val json = loadJsonFile(file)
      json match {
        case Some(content) =>
          try {
            val parsed = parseJson(content)
            val words = format match {
              case "json-simple"  => extractFromSimple(parsed)
              case "json-full"    => extractFromFull(parsed)
              case "json-sentence" => extractFromSentence(parsed)
              case _              => List.empty
            }
            println(s"    加载 $file: ${words.size} 词")
            words
          } catch {
            case e: Exception =>
              println(s"    解析失败 $file: ${e.getMessage}")
              List.empty
          }
        case None =>
          println(s"    未找到文件: $file")
          List.empty
      }
    }
  }

  def loadJsonFile(resourceName: String): Option[String] = {
    var stream = getClass.getClassLoader.getResourceAsStream(resourceName)
    if (stream == null) stream = getClass.getResourceAsStream("/" + resourceName)
    if (stream == null) stream = getClass.getResourceAsStream(resourceName)
    if (stream != null) {
      val source = Source.fromInputStream(stream, "UTF-8")
      val text = source.mkString
      source.close()
      val cleaned = if (text.nonEmpty && text.head == '\ufeff') text.tail else text
      Some(cleaned)
    } else {
      None
    }
  }

  // ==================== JSON解析器 ====================

  var pos: Int = 0
  var src: String = ""

  def parseJson(input: String): Any = {
    src = input
    pos = 0
    skipWs()
    parseVal()
  }

  def skipWs(): Unit = {
    while (pos < src.length && " \t\n\r".indexOf(src(pos)) >= 0) pos += 1
  }

  def parseVal(): Any = {
    skipWs()
    if (pos >= src.length) return null
    src(pos) match {
      case '{' => parseObj()
      case '[' => parseArr()
      case '"' => parseStr()
      case 't' | 'f' => parseBool()
      case 'n' if pos + 3 < src.length && src.substring(pos, pos + 4) == "null" =>
        pos += 4; null
      case c if c == '-' || c.isDigit => parseNum()
      case _ => pos += 1; null
    }
  }

  def parseStr(): String = {
    if (pos >= src.length || src(pos) != '"') return ""
    pos += 1
    val sb = new StringBuilder
    while (pos < src.length && src(pos) != '"') {
      if (src(pos) == '\\' && pos + 1 < src.length) {
        pos += 1
        src(pos) match {
          case '"'  => sb.append('"')
          case '\\' => sb.append('\\')
          case '/'  => sb.append('/')
          case 'n'  => sb.append('\n')
          case 'r'  => sb.append('\r')
          case 't'  => sb.append('\t')
          case 'b'  => sb.append('\b')
          case 'f'  => sb.append('\f')
          case 'u' if pos + 4 < src.length =>
            val hex = src.substring(pos + 1, pos + 5)
            try { sb.append(Integer.parseInt(hex, 16).toChar) } catch { case _: Exception => }
            pos += 4
          case c => sb.append(c)
        }
      } else {
        sb.append(src(pos))
      }
      pos += 1
    }
    if (pos < src.length) pos += 1
    sb.toString
  }

  def parseNum(): Double = {
    val start = pos
    if (pos < src.length && src(pos) == '-') pos += 1
    while (pos < src.length && src(pos).isDigit) pos += 1
    if (pos < src.length && src(pos) == '.') {
      pos += 1
      while (pos < src.length && src(pos).isDigit) pos += 1
    }
    if (pos < src.length && (src(pos) == 'e' || src(pos) == 'E')) {
      pos += 1
      if (pos < src.length && (src(pos) == '+' || src(pos) == '-')) pos += 1
      while (pos < src.length && src(pos).isDigit) pos += 1
    }
    try { src.substring(start, pos).toDouble } catch { case _: Exception => 0.0 }
  }

  def parseBool(): Boolean = {
    if (src.startsWith("true", pos)) { pos += 4; true }
    else { pos += 5; false }
  }

  def parseObj(): Map[String, Any] = {
    pos += 1
    val map = mutable.Map[String, Any]()
    skipWs()
    if (pos < src.length && src(pos) == '}') { pos += 1; return map.toMap }
    while (pos < src.length) {
      skipWs()
      if (pos >= src.length || src(pos) != '"') return map.toMap
      val key = parseStr()
      skipWs()
      if (pos < src.length && src(pos) == ':') pos += 1
      val value = parseVal()
      map(key) = value
      skipWs()
      if (pos < src.length && src(pos) == ',') pos += 1
      else { skipWs(); if (pos < src.length && src(pos) == '}') pos += 1; return map.toMap }
    }
    map.toMap
  }

  def parseArr(): List[Any] = {
    pos += 1
    val buf = ListBuffer[Any]()
    skipWs()
    if (pos < src.length && src(pos) == ']') { pos += 1; return buf.toList }
    while (pos < src.length) {
      val v = parseVal()
      buf += v
      skipWs()
      if (pos < src.length && src(pos) == ',') pos += 1
      else { skipWs(); if (pos < src.length && src(pos) == ']') pos += 1; return buf.toList }
    }
    buf.toList
  }

  // ==================== JSON辅助方法 ====================

  def toMap(v: Any): Map[String, Any] = v match {
    case m: Map[_, _] => m.map { case (k, v) => (k.toString, v) }
    case _ => Map.empty[String, Any]
  }

  def toList(v: Any): List[Any] = v match {
    case l: List[_] => l
    case _ => List()
  }

  def str(v: Any): String = v match {
    case s: String => s
    case _ => ""
  }

  def getField(m: Map[String, Any], keys: String*): Any = {
    keys.flatMap(k => m.get(k)).headOption.getOrElse(null)
  }

  def findKeyDeep(v: Any, key: String): List[Any] = {
    val result = ListBuffer[Any]()
    v match {
      case m: Map[_, _] =>
        val map = m.asInstanceOf[Map[Any, Any]]
        map.foreach { case (k, v2) =>
          if (k.toString == key) result += v2
          result ++= findKeyDeep(v2, key)
        }
      case l: List[_] =>
        l.foreach(item => result ++= findKeyDeep(item, key))
      case _ =>
    }
    result.toList
  }

  // ==================== 数据提取 ====================

  def extractFromSimple(parsed: Any): List[Word] = {
    toList(parsed).flatMap { item =>
      val m = toMap(item)
      val word = str(m.getOrElse("word", ""))
      if (word.isEmpty) None
      else {
        val trans = extractTranslations(m)
        val phrases = extractPhrases(m)
        Some(Word(word, trans, extractPosSet(trans), phrases.size))
      }
    }
  }

  def extractFromFull(parsed: Any): List[Word] = {
    val items = parsed match {
      case l: List[_] =>
        val first = l.headOption
        first match {
          case Some(m: Map[_, _]) if toMap(m).contains("headWord") => l
          case _ => findKeyDeep(parsed, "headWord")
        }
      case m: Map[_, _] =>
        if (toMap(m).contains("headWord")) List(parsed)
        else findKeyDeep(parsed, "headWord")
      case _ => List()
    }

    items.flatMap { item =>
      val m = toMap(item)
      val word = str(getField(m, "headWord", "word"))
      if (word.isEmpty) None
      else {
        val content = toMap(m.getOrElse("content", Map.empty))
        val wordObj = toMap(content.getOrElse("word", Map.empty))
        val innerContent = toMap(wordObj.getOrElse("content", Map.empty))

        val transList = toList(innerContent.getOrElse("trans", List.empty))
        val translations = transList.flatMap { t =>
          val tm = toMap(t)
          val cn = str(tm.getOrElse("tranCn", ""))
          val p = str(tm.getOrElse("pos", ""))
          if (cn.nonEmpty) Some((cn, p)) else None
        }

        val phraseObj = toMap(innerContent.getOrElse("phrase", Map.empty))
        val phrases = toList(phraseObj.getOrElse("phrases", List.empty)).map(p =>
          str(toMap(p).getOrElse("pContent", ""))
        ).filter(_.nonEmpty)

        Some(Word(word, translations, extractPosSet(translations), phrases.size))
      }
    }
  }

  def extractFromSentence(parsed: Any): List[Word] = {
    toList(parsed).flatMap { item =>
      val m = toMap(item)
      val word = str(m.getOrElse("word", ""))
      if (word.isEmpty) None
      else {
        val trans = extractTranslations(m)
        val phrases = extractPhrases(m)
        Some(Word(word, trans, extractPosSet(trans), phrases.size))
      }
    }
  }

  def extractTranslations(m: Map[String, Any]): List[(String, String)] = {
    toList(m.getOrElse("translations", List.empty)).flatMap { t =>
      val tm = toMap(t)
      val translation = str(tm.getOrElse("translation", ""))
      val tpe = str(getField(tm, "type", "pos"))
      if (translation.nonEmpty) Some((translation, tpe)) else None
    }
  }

  def extractPhrases(m: Map[String, Any]): List[String] = {
    toList(m.getOrElse("phrases", List.empty)).flatMap { p =>
      val pm = toMap(p)
      val phrase = str(getField(pm, "phrase", "pContent"))
      if (phrase.nonEmpty) Some(phrase) else None
    }
  }

  def extractPosSet(translations: List[(String, String)]): Set[String] = {
    translations.map(_._2).filter(_.nonEmpty).map(_.trim.toLowerCase).toSet
  }
}
