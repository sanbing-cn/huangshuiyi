import scala.io.Source
import scala.collection.mutable

object SidaMingzhu {

  def main(args: Array[String]): Unit = {
    println("=" * 80)
    println("          四大名著数据分析系统")
    println("=" * 80)

    val bookFiles = Map(
      "三国演义" -> "中文分词/三国演义.txt",
      "水浒传" -> "中文分词/水浒传.txt",
      "西游记" -> "中文分词/西游记.txt",
      "红楼梦" -> "中文分词/红楼梦.txt"
    )


    val novels = loadNovels(bookFiles)

    if (novels.isEmpty) {
      println("\n错误：未加载到任何名著数据！")
      println("请确保在 src/main/resources/四大名著/ 目录下放置以下文件：")
      bookFiles.values.foreach(f => println(s"  - $f"))
      return
    }

    println(s"\n成功加载 ${novels.size} 部名著\n")

    // 1. 名著基本信息统计
    basicStatistics(novels)

    // 2. 词频统计（每部高频词、四部对比、人名/地名/官职/武器）
    wordFrequencyAnalysis(novels, 30)

    // 3. 情感分析
    emotionAnalysis(novels)

    // 4. 人物关系图谱构建、阵营对抗（三国演义）
    threeKingdomsAnalysis(novels)
  }

  // ==================== 数据加载 ====================

  def loadNovels(bookFiles: Map[String, String]): List[Novel] = {
    bookFiles.map { case (name, path) =>
      println(s"正在加载: $name ($path)")
      val content = loadTextFromClasspath(path)
      content match {
        case Some(text) =>
          val chapters = splitChapters(text)
          println(s"  成功: 总字数=${text.length}, 章节数=${chapters.size}")
          Some(Novel(name, text, chapters))
        case None =>
          println(s"  未找到文件，跳过")
          None
      }
    }.toList.flatten
  }

  def loadTextFromClasspath(resourceName: String): Option[String] = {
    var stream = getClass.getClassLoader.getResourceAsStream(resourceName)
    if (stream == null) stream = getClass.getResourceAsStream("/" + resourceName)
    if (stream == null) stream = getClass.getResourceAsStream(resourceName)

    if (stream != null) {
      val source = Source.fromInputStream(stream, "GBK")
      val text = source.mkString
      source.close()
      Some(text)
    } else {
      None
    }
  }

  def splitChapters(text: String): List[String] = {
    val chapterPattern = """(?=第[一二三四五六七八九十百千零〇\d]+回[\s])""".r
    val chapters = chapterPattern.split(text).filter(_.trim.nonEmpty).toList
    if (chapters.size > 1) chapters else List(text)
  }

  // ==================== 1. 基本信息统计 ====================

  def basicStatistics(novels: List[Novel]): Unit = {
    println("\n" + "=" * 80)
    println("一、名著基本信息统计")
    println("=" * 80)

    println(f"\n${"书名"}%-12s ${"总字数"}%10s ${"章节数"}%8s ${"平均章节字数"}%14s ${"词汇丰富度"}%12s")
    println("-" * 70)

    novels.foreach { novel =>
      val totalChars = novel.content.length
      val chineseChars = novel.content.count(c => c >= '\u4e00' && c <= '\u9fff')
      val chapterCount = novel.chapters.size
      val avgChapterLen = if (chapterCount > 0) chineseChars / chapterCount else chineseChars
      val uniqueChars = novel.content.filter(c => c >= '\u4e00' && c <= '\u9fff').distinct.length
      println(f"${novel.name}%-12s $chineseChars%10d $chapterCount%8d $avgChapterLen%14d $uniqueChars%12s")
    }

    println("\n各书主题风格关键词分析:")
    println("-" * 70)

    val styleKeywords = Map(
      "战争谋略" -> List("战", "兵", "军", "谋", "计", "阵", "攻", "守", "将", "帅", "旗", "鼓"),
      "英雄侠义" -> List("义", "侠", "勇", "猛", "威", "胆", "力", "刚", "烈", "豪", "气", "血"),
      "神魔奇幻" -> List("妖", "魔", "仙", "神", "法", "术", "宝", "洞", "天", "地", "变", "化"),
      "人情世故" -> List("情", "爱", "恨", "怨", "恩", "仇", "亲", "友", "家", "族", "婚", "嫁"),
      "忠义精神" -> List("忠", "义", "孝", "节", "烈", "信", "仁", "德", "礼", "智", "廉", "耻"),
      "自然描写" -> List("山", "水", "月", "风", "花", "雪", "云", "雨", "春", "秋", "日", "星")
    )

    novels.foreach { novel =>
      println(s"\n  【${novel.name}】")
      styleKeywords.foreach { case (style, keywords) =>
        val count = keywords.count(kw => novel.content.contains(kw))
        val bar = "█" * count
        println(f"    $style: $count%3d  $bar")
      }
    }
  }

  // ==================== 2. 词频统计 ====================

  def wordFrequencyAnalysis(novels: List[Novel], topN: Int): Unit = {
    println("\n" + "=" * 80)
    println("二、词频统计分析")
    println("=" * 80)

    val stopWords = getStopWords

    // 每部名著的高频词
    novels.foreach { novel =>
      println(s"\n【${novel.name}】高频词 TOP$topN:")
      println("-" * 60)

      val words = segmentText(novel.content)
      val filtered = words.filterNot(stopWords.contains)
      val wordFreq = filtered.groupBy(identity).mapValues(_.size).toList.sortBy(-_._2)

      println("排名\t词汇\t出现次数\t频率(‱)")
      wordFreq.take(topN).zipWithIndex.foreach { case ((word, count), idx) =>
        val freq = count.toDouble / filtered.size * 10000
        println(f"  ${idx + 1}%3d.\t$word\t$count%6d\t$freq%.2f‱")
      }
    }

    // 四部名著对比 —— 共有高频词 vs 各书独有高频词
    println(s"\n\n四部名著高频词对比 (各取TOP$topN):")
    println("=" * 60)

    val bookTopWords = novels.map { novel =>
      val words = segmentText(novel.content).filterNot(stopWords.contains)
      val topWords = words.groupBy(identity).mapValues(_.size).toList.sortBy(-_._2).take(topN).map(_._1).toSet
      (novel.name, topWords)
    }.toMap

    val allTopWords = bookTopWords.values.foldLeft(Set.empty[String])(_ ++ _)

    println("\n各书独有高频词（其他三本书TOP中未出现的）:")
    println("-" * 60)
    bookTopWords.foreach { case (bookName, topWords) =>
      val otherWords = bookTopWords.filterKeys(_ != bookName).values.foldLeft(Set.empty[String])(_ ++ _)
      val uniqueWords = topWords -- otherWords
      println(s"\n  【$bookName】独有: ${uniqueWords.take(15).mkString("、")}")
    }

    val commonWords = allTopWords.filter(w => bookTopWords.values.count(tv => tv.contains(w)) >= 3)

    println(s"\n  四部共有高频词: ${commonWords.take(20).mkString("、")}")

    // 人名、地名、官职、武器名 专项统计
    println("\n\n" + "=" * 80)
    println("人名、地名、官职、武器名 专项统计")
    println("=" * 80)

    novels.foreach { novel =>
      println(s"\n${"=" * 40}")
      println(s"【${novel.name}】")
      println(s"${"=" * 40}")

      val (names, places, titles, weapons) = getDictionaries(novel.name)

      println(s"\n  人名出现频次:")
      val nameStats = countKeywords(novel.content, names).take(15)
      nameStats.foreach { case (name, count) => println(f"    $name%-8s: $count%5d 次") }

      println(s"\n  地名出现频次:")
      val placeStats = countKeywords(novel.content, places).take(10)
      placeStats.foreach { case (place, count) => println(f"    $place%-8s: $count%5d 次") }

      println(s"\n  官职出现频次:")
      val titleStats = countKeywords(novel.content, titles).take(10)
      titleStats.foreach { case (title, count) => println(f"    $title%-10s: $count%5d 次") }

      println(s"\n  武器/兵器出现频次:")
      val weaponStats = countKeywords(novel.content, weapons).take(10)
      weaponStats.foreach { case (weapon, count) => println(f"    $weapon%-10s: $count%5d 次") }
    }
  }

  // ==================== 3. 情感分析 ====================

  def emotionAnalysis(novels: List[Novel]): Unit = {
    println("\n" + "=" * 80)
    println("三、情感词汇分析")
    println("=" * 80)

    val emotionCategories = Map(
      "褒义/赞美" -> List("忠", "义", "勇", "猛", "智", "慧", "仁", "德", "贤", "良", "善", "美",
        "刚", "烈", "豪", "杰", "英", "伟", "俊", "秀", "孝", "节", "廉", "耻",
        "圣", "明", "清", "正", "直", "诚", "信", "敬", "恭", "俭", "让"),
      "贬义/批评" -> List("奸", "邪", "恶", "毒", "狠", "残", "暴", "虐", "贪", "赃", "枉", "法",
        "贼", "盗", "匪", "魔", "妖", "怪", "丑", "陋", "愚", "蠢", "笨", "庸",
        "伪", "诈", "奸", "佞", "谄", "媚", "骄", "傲", "奢", "侈"),
      "喜悦/欢乐" -> List("喜", "乐", "欢", "笑", "庆", "贺", "欣", "悦", "畅", "怡", "快", "幸",
        "福", "甜", "美", "好", "妙", "佳", "吉", "祥", "如", "意"),
      "愤怒/激烈" -> List("怒", "愤", "恨", "恼", "火", "气", "怨", "骂", "斥", "责", "吼", "嚎",
        "咆", "哮", "冲", "冠", "发", "冲", "震", "惊"),
      "悲伤/哀愁" -> List("悲", "伤", "哀", "痛", "哭", "泣", "泪", "愁", "苦", "惨", "凄", "凉",
        "惨", "淡", "寞", "寂", "寥", "孤", "独", "徨"),
      "恐惧/紧张" -> List("怕", "惧", "恐", "惊", "慌", "忙", "急", "忙", "乱", "逃", "窜", "躲",
        "避", "退", "缩", "颤", "抖", "战", "兢")
    )

    novels.foreach { novel =>
      println(s"\n【${novel.name}】情感词汇分析:")
      println("-" * 70)

      val emotionCounts = emotionCategories.map { case (emotion, words) =>
        val count = words.map(w => novel.content.sliding(w.length).count(_ == w)).sum
        (emotion, count)
      }.toList

      emotionCounts.foreach { case (emotion, count) =>
        val barLen = if (count >= 50) count / 50 else 0
        val bar = "█" * barLen
        println(f"  $emotion%-12s: $count%5d 次  $bar")
      }

      val positiveCount = emotionCounts.find(_._1 == "褒义/赞美").map(_._2).getOrElse(0)
      val negativeCount = emotionCounts.find(_._1 == "贬义/批评").map(_._2).getOrElse(0)
      val joyCount = emotionCounts.find(_._1 == "喜悦/欢乐").map(_._2).getOrElse(0)
      val angerCount = emotionCounts.find(_._1 == "愤怒/激烈").map(_._2).getOrElse(0)
      val sadCount = emotionCounts.find(_._1 == "悲伤/哀愁").map(_._2).getOrElse(0)

      println(f"\n  情感倾向: 褒义($positiveCount) vs 贬义($negativeCount) => " +
        (if (positiveCount > negativeCount) "整体偏正面" else "整体偏负面"))
      println(f"  情绪分布: 喜($joyCount) / 怒($angerCount) / 哀($sadCount) => " + {
        val maxEmotion = List(("喜", joyCount), ("怒", angerCount), ("哀", sadCount)).sortBy(-_._2).head
        s"${maxEmotion._1}情为主"
      })
    }

    // 四部名著情感对比
    println("\n\n四部名著情感对比汇总:")
    println("-" * 70)
    println(f"${"书名"}%-12s ${"褒义"}%8s ${"贬义"}%8s ${"喜悦"}%8s ${"愤怒"}%8s ${"悲伤"}%8s ${"褒贬比"}%10s")
    novels.foreach { novel =>
      val pos = emotionCategories("褒义/赞美").map(w => novel.content.sliding(w.length).count(_ == w)).sum
      val neg = emotionCategories("贬义/批评").map(w => novel.content.sliding(w.length).count(_ == w)).sum
      val joy = emotionCategories("喜悦/欢乐").map(w => novel.content.sliding(w.length).count(_ == w)).sum
      val anger = emotionCategories("愤怒/激烈").map(w => novel.content.sliding(w.length).count(_ == w)).sum
      val sad = emotionCategories("悲伤/哀愁").map(w => novel.content.sliding(w.length).count(_ == w)).sum
      val ratio = if (neg > 0) f"${pos.toDouble / neg}%.2f" else "N/A"
      println(f"${novel.name}%-12s $pos%8d $neg%8d $joy%8d $anger%8d $sad%8d $ratio%10s")
    }
  }

  // ==================== 4. 三国演义专项分析 ====================

  def threeKingdomsAnalysis(novels: List[Novel]): Unit = {
    val sgyy = novels.find(_.name == "三国演义")
    if (sgyy.isEmpty) {
      println("\n未找到《三国演义》数据，跳过人物关系分析")
      return
    }

    val novel = sgyy.get
    println("\n" + "=" * 80)
    println("四、三国演义 - 人物关系图谱与阵营对抗分析")
    println("=" * 80)

    val text = novel.content

    // 定义阵营
    val factions = Map(
      "魏阵营" -> List("曹操", "曹丕", "司马懿", "夏侯惇", "夏侯渊", "许褚", "典韦", "荀彧", "郭嘉",
        "程昱", "张辽", "徐晃", "于禁", "乐进", "李典", "曹仁", "曹洪",
        "荀攸", "贾诩", "张郃", "庞德", "满宠", "蒋济", "司马昭", "司马师"),
      "蜀阵营" -> List("刘备", "关羽", "张飞", "诸葛亮", "赵云", "马超", "黄忠", "魏延", "庞统",
        "姜维", "关平", "周仓", "法正", "黄权", "马谡", "王平", "关兴", "张苞",
        "刘禅", "徐庶", "严颜", "孙乾", "糜竺", "简雍"),
      "吴阵营" -> List("孙权", "周瑜", "鲁肃", "吕蒙", "陆逊", "甘宁", "太史慈", "黄盖", "程普",
        "韩当", "孙策", "孙坚", "大乔", "小乔", "凌统", "周泰", "丁奉", "徐盛",
        "诸葛瑾", "张昭", "顾雍"),
      "其他势力" -> List("吕布", "貂蝉", "董卓", "袁绍", "袁术", "刘表", "刘璋", "公孙瓒",
        "张角", "张宝", "张梁", "华佗", "司马徽", "左慈", "于吉", "孟获", "祝融")
    )

    val allCharacters = factions.values.flatten.toList
    val characterNames = allCharacters.sortBy(-_.length)

    // (1) 人物出场频次
    println("\n(1) 主要人物出场频次:")
    println("-" * 70)
    val charFreq = characterNames.map(c => (c, countWord(text, c))).filter(_._2 > 0).sortBy(-_._2)
    charFreq.take(30).zipWithIndex.foreach { case ((name, count), idx) =>
      val bar = "█" * (if (count >= 20) count / 20 else 0)
      println(f"  ${idx + 1}%3d. $name%-8s: $count%5d 次  $bar")
    }

    // (2) 人物共现关系（简化版关系图谱）
    println("\n\n(2) 人物共现关系统计（基于章节共现）:")
    println("-" * 70)

    val topChars = charFreq.take(25).map(_._1)
    val topCharsSorted = topChars.sortBy(-_.length)
    val windowSize = 100

    val cooccurrence = mutable.Map[(String, String), Int]().withDefaultValue(0)

    topChars.foreach(a => topChars.foreach(b => {
      if (a != b) cooccurrence((a, b)) = 0
    }))

    novel.chapters.foreach { chapter =>
      val presentChars = topCharsSorted.filter(c => chapter.contains(c)).distinct
      for (i <- presentChars.indices; j <- (i + 1) until presentChars.size) {
        val pair = if (presentChars(i) < presentChars(j))
          (presentChars(i), presentChars(j))
        else
          (presentChars(j), presentChars(i))
        cooccurrence(pair) += 1
      }
    }

    // 补充滑动窗口共现
    text.sliding(windowSize).foreach { window =>
      val presentChars = topCharsSorted.filter(c => window.contains(c)).distinct
      for (i <- presentChars.indices; j <- (i + 1) until presentChars.size) {
        val pair = if (presentChars(i) < presentChars(j))
          (presentChars(i), presentChars(j))
        else
          (presentChars(j), presentChars(i))
        cooccurrence(pair) += 1
      }
    }

    val topRelations = cooccurrence.toList.filter(_._2 > 0).sortBy(-_._2).take(30)
    println("\n  共现频次TOP30（可据此构建关系图谱）:")
    println("  人物A        人物B        共现次数")
    topRelations.foreach { case ((a, b), count) =>
      val relationType = if (count > 200) "★★★★★" else if (count > 100) "★★★★" else if (count > 50) "★★★" else if (count > 20) "★★" else "★"
      println(f"  $a%-12s $b%-12s $count%6d  $relationType")
    }

    // (3) 阵营分析
    println("\n\n(3) 阵营势力分析:")
    println("-" * 70)

    val factionCharCounts = factions.map { case (factionName, members) =>
      val totalMentions = members.map(c => countWord(text, c)).sum
      (factionName, members, totalMentions)
    }.toList.sortBy(-_._3)

    factionCharCounts.foreach { case (factionName, members, total) =>
      println(s"\n  【$factionName】总提及: $total 次, 人物数: ${members.size} 人")
      val memberMentions = members.map(m => (m, countWord(text, m))).filter(_._2 > 0).sortBy(-_._2).take(8)
      memberMentions.foreach { case (name, count) =>
        println(f"    $name%-10s: $count%5d 次")
      }
    }

    // (4) 阵营对抗分析
    println("\n\n(4) 阵营对抗分析（跨阵营人物共现 = 对抗/交互）:")
    println("-" * 70)

    val charToFaction = factions.flatMap { case (factionName, members) =>
      members.map(m => m -> factionName)
    }

    val crossFactionPairs = cooccurrence.toList.filter { case ((a, b), _) =>
      charToFaction.contains(a) && charToFaction.contains(b) &&
        charToFaction(a) != charToFaction(b)
    }.sortBy(-_._2).take(25)

    println("\n  跨阵营交互TOP25:")
    println("  人物A          阵营      人物B          阵营      交互次数")
    crossFactionPairs.foreach { case ((a, b), count) =>
      val fa = charToFaction.getOrElse(a, "未知")
      val fb = charToFaction.getOrElse(b, "未知")
      println(f"  $a%-12s ${fa}%-10s $b%-12s ${fb}%-10s $count%6d")
    }

    // 阵营间总交互统计
    println("\n  阵营间总交互强度:")
    val factionPairs = mutable.Map[(String, String), Int]().withDefaultValue(0)
    crossFactionPairs.foreach { case ((a, b), count) =>
      val fa = charToFaction(a)
      val fb = charToFaction(b)
      val key = if (fa < fb) (fa, fb) else (fb, fa)
      factionPairs(key) += count
    }

    factionPairs.toList.sortBy(-_._2).foreach { case ((fa, fb), count) =>
      val bar = "█" * (if (count >= 50) count / 50 else 0)
      println(f"    $fa vs $fb: $count%6d 次  $bar")
    }

    // (5) 关系图谱文本表示
    println("\n\n(5) 核心人物关系图谱（文本表示）:")
    println("-" * 70)

    val coreChars = charFreq.take(10).map(_._1).sorted
    val coreSorted = coreChars.sortBy(-_.length)

    coreSorted.foreach { charA =>
      val related = topRelations
        .filter { case ((a, b), _) => a == charA || b == charA }
        .map { case ((a, b), count) =>
          val other = if (a == charA) b else a
          (other, count)
        }
        .sortBy(-_._2)
        .take(5)

      if (related.nonEmpty) {
        val faction = charToFaction.get(charA).getOrElse("其他")
        val relatedStr = related.map { case (name, count) => s"$name($count)" }.mkString(", ")
        println(s"  [$charA]($faction) --> $relatedStr")
      }
    }
  }

  // ==================== 工具方法 ====================

  def segmentText(text: String): List[String] = {
    text.filter(c => c >= '\u4e00' && c <= '\u9fff').map(_.toString).toList
  }

  def countWord(text: String, word: String): Int = {
    if (word.isEmpty) 0
    else text.sliding(word.length).count(_ == word)
  }

  def countKeywords(text: String, keywords: List[String]): List[(String, Int)] = {
    keywords.map(kw => (kw, countWord(text, kw))).filter(_._2 > 0).sortBy(-_._2)
  }

  def getStopWords: Set[String] = {
    Set("的", "了", "是", "在", "之", "乎", "者", "也", "而", "其", "以", "于", "为",
      "有", "不", "人", "中", "大", "上", "下", "我", "他", "她", "它", "们",
      "这", "那", "被", "把", "让", "给", "从", "到", "向", "对", "和", "与",
      "或", "但", "又", "再", "还", "就", "都", "只", "又", "很", "更", "最",
      "没", "无", "非", "若", "如", "则", "乃", "即", "且", "虽", "然", "故",
      "曰", "道", "想", "看", "来", "去", "得", "着", "过", "个", "些", "么",
      "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "百", "千",
      "万", "两", "几", "多", "少", "此", "彼", "各", "每", "某", "该",
      " ", "", "\u3000", "\n", "\r", "\t",
      "一个", "这个", "那个", "什么", "怎么", "为什么", "如何", "怎样",
      "可以", "可能", "应该", "必须", "需要", "能够", "已经", "正在",
      "不是", "没有", "不能", "不会", "不敢")
  }

  def getDictionaries(bookName: String): (List[String], List[String], List[String], List[String]) = {
    bookName match {
      case "三国演义" =>
        val names = List(
          "诸葛亮", "司马懿", "司马昭", "司马师", "夏侯惇", "夏侯渊",
          "曹操", "曹丕", "曹仁", "曹洪", "曹真", "曹爽",
          "刘备", "刘禅", "刘表", "刘璋",
          "关羽", "关平", "关兴",
          "张飞", "张苞", "张辽", "张郃", "张角", "张宝", "张梁", "张昭", "张翼",
          "赵云", "赵统",
          "孙权", "孙策", "孙坚", "孙乾",
          "周瑜", "周仓", "周泰",
          "马超", "马谡", "马岱", "马腾",
          "黄忠", "黄盖", "黄权",
          "魏延", "庞统", "庞德",
          "姜维", "蒋琬", "费祎",
          "吕布", "貂蝉", "董卓", "袁绍", "袁术",
          "许褚", "典韦", "徐晃", "于禁", "乐进", "李典",
          "荀彧", "荀攸", "郭嘉", "程昱", "贾诩", "满宠",
          "鲁肃", "吕蒙", "陆逊", "甘宁", "太史慈", "丁奉", "徐盛", "凌统",
          "法正", "徐庶", "严颜", "王平", "诸葛瑾",
          "华佗", "左慈", "于吉", "司马徽", "孟获", "祝融",
          "公孙瓒", "刘晔", "陈宫", "审配", "田丰", "沮授", "颜良", "文丑"
        )
        val places = List("荆州", "益州", "徐州", "兖州", "豫州", "冀州", "并州", "青州", "凉州", "雍州",
          "洛阳", "许昌", "成都", "建业", "汉中", "襄阳", "樊城", "江陵", "公安",
          "赤壁", "长坂", "五丈原", "定军山", "麦城", "街亭", "汉中",
          "许昌", "邺城", "南郡", "江夏", "长沙", "武陵", "桂阳", "零陵",
          "汉中", "葭萌关", "剑阁", "阳平关", "潼关", "虎牢关", "函谷关",
          "黄河", "长江", "渭水", "汉水")
        val titles = List("丞相", "大将军", "军师", "太守", "刺史", "尚书", "侍郎", "长史",
          "司马", "参军", "主簿", "从事", "都督", "督军", "先锋", "后卫",
          "皇帝", "主公", "殿下", "陛下", "大王", "侯", "王", "公",
          "关内侯", "武乡侯", "汉寿亭侯", "魏王", "吴王", "汉中王")
        val weapons = List("青龙偃月刀", "丈八蛇矛", "方天画戟", "雌雄双股剑", "倚天剑", "青釭剑",
          "赤兔马", "的卢马", "绝影", "爪黄飞电",
          "弓箭", "弩", "刀", "枪", "戟", "斧", "锤", "鞭",
          "铁戟", "大刀", "长枪", "强弓", "硬弩", "火箭", "战车")
        (names, places, titles, weapons)

      case "水浒传" =>
        val names = List(
          "宋江", "卢俊义", "吴用", "公孙胜", "关胜", "林冲", "秦明", "呼延灼", "花荣",
          "柴进", "李应", "朱仝", "鲁智深", "武松", "董平", "张清", "杨志", "徐宁",
          "索超", "戴宗", "刘唐", "李逵", "史进", "穆弘", "雷横", "李俊", "阮小二",
          "张横", "阮小五", "张顺", "阮小七", "杨雄", "石秀", "解珍", "解宝",
          "燕青", "朱武", "黄信", "孙立", "宣赞", "郝思文", "韩滔", "彭玘",
          "扈三娘", "孙二娘", "顾大嫂",
          "高俅", "蔡京", "童贯", "杨戬", "宋徽宗",
          "晁盖", "王伦", "史文恭", "栾廷玉", "曾头市",
          "镇关西", "蒋门神", "西门庆", "潘金莲", "阎婆惜", "孙押司"
        )
        val places = List("梁山泊", "水泊", "忠义堂", "东京", "开封", "汴梁",
          "郓城", "阳谷县", "孟州", "沧州", "渭州", "代州",
          "景阳冈", "快活林", "飞云浦", "鸳鸯楼", "蜈蚣岭",
          "江州", "浔阳楼", "梁山", "二龙山", "桃花山", "少华山",
          "大名府", "曾头市", "祝家庄", "扈家庄", "李家庄")
        val titles = List("及时雨", "呼保义", "玉麒麟", "智多星", "入云龙", "大刀",
          "豹子头", "霹雳火", "双鞭", "小李广", "小旋风", "花和尚", "行者",
          "青面兽", "金枪手", "黑旋风", "浪子", "母夜叉", "一丈青",
          "押司", "都头", "提辖", "教头", "知寨", "知县", "知府",
          "太尉", "丞相", "枢密", "统制", "都监", "团练")
        val weapons = List("哨棒", "朴刀", "禅杖", "戒刀", "解腕尖刀",
          "丈八蛇矛", "青龙刀", "双斧", "双刀", "长枪",
          "弓箭", "弩", "飞刀", "飞叉", "钢叉",
          "拳脚", "棍棒", "枪棒", "水火棍")
        (names, places, titles, weapons)

      case "西游记" =>
        val names = List(
          "孙悟空", "行者", "大圣", "齐天大圣", "美猴王", "猴王", "悟空",
          "唐僧", "唐三藏", "三藏", "御弟", "长老", "师父",
          "猪八戒", "八戒", "猪悟能", "天蓬元帅",
          "沙僧", "沙悟净", "沙和尚",
          "白龙马", "小龙王", "龙王三太子",
          "观音", "观音菩萨", "如来", "如来佛", "玉帝", "玉皇大帝",
          "太上老君", "太白金星", "托塔李天王", "哪吒", "二郎神",
          "菩提祖师", "镇元子", "太乙真人",
          "牛魔王", "铁扇公主", "红孩儿",
          "白骨精", "蜘蛛精", "蝎子精", "玉兔精", "琵琶精",
          "金角大王", "银角大王", "黄风怪", "黑风怪", "熊罴怪",
          "黄袍怪", "灵感大王", "赛太岁", "九灵元圣",
          "李天王", "巨灵神", "四大天王", "二十八宿",
          "唐太宗", "魏征", "泾河龙王", "女儿国国王", "天竺国公主"
        )
        val places = List("花果山", "水帘洞", "五行山", "两界山",
          "高老庄", "流沙河", "鹰愁涧",
          "火焰山", "翠云山", "芭蕉洞",
          "盘丝洞", "黄花观", "狮驼岭", "狮驼国",
          "女儿国", "天竺国", "宝象国", "乌鸡国", "车迟国", "朱紫国",
          "五庄观", "碧波潭", "通天河", "黑水河", "子母河",
          "灵山", "大雷音寺", "南海", "普陀山", "天庭", "凌霄殿",
          "兜率宫", "蟠桃园", "瑶池", "龙宫", "地府", "冥界",
          "长安", "大唐")
        val titles = List("大圣", "大王", "佛祖", "菩萨", "天尊", "天尊",
          "天王", "太子", "星君", "真人", "祖师",
          "皇帝", "陛下", "殿下", "国王", "驸马",
          "师父", "师傅", "长老", "和尚", "道士", "禅师",
          "妖怪", "妖精", "妖魔", "魔头",
          "天蓬元帅", "卷帘大将", "弼马温")
        val weapons = List("金箍棒", "如意金箍棒", "九齿钉耙", "降妖宝杖",
          "宝剑", "飞剑", "斩妖剑", "砍妖刀",
          "紫金铃", "金刚琢", "芭蕉扇", "幌金绳",
          "人种袋", "金铙", "玉净瓶", "莲花座",
          "火尖枪", "三尖两刃枪", "混天绫", "乾坤圈",
          "筋斗云", "避水诀", "七十二变", "定身法")
        (names, places, titles, weapons)

      case "红楼梦" =>
        val names = List(
          "贾宝玉", "宝玉", "宝二爷",
          "林黛玉", "黛玉", "颦儿", "林姑娘",
          "薛宝钗", "宝钗", "宝姑娘", "宝姐姐",
          "王熙凤", "凤姐", "凤辣子", "琏二奶奶",
          "贾母", "老太太", "史太君",
          "贾政", "贾赦", "贾珍", "贾琏", "贾环", "贾蓉", "贾兰",
          "王夫人", "邢夫人", "尤氏", "李纨",
          "贾元春", "元春", "贾迎春", "迎春", "贾探春", "探春", "贾惜春", "惜春",
          "史湘云", "湘云",
          "妙玉", "巧姐", "秦可卿", "可卿",
          "晴雯", "袭人", "平儿", "鸳鸯", "紫鹃", "雪雁", "香菱",
          "司棋", "侍书", "入画", "麝月", "秋纹", "碧痕",
          "薛蟠", "薛姨妈", "夏金桂",
          "刘姥姥", "板儿",
          "北静王", "忠顺王",
          "贾雨村", "甄士隐", "柳湘莲", "尤三姐", "尤二姐",
          "秦钟", "蒋玉菡", "琪官"
        )
        val places = List("荣国府", "宁国府", "大观园",
          "怡红院", "潇湘馆", "蘅芜苑", "稻香村", "秋爽斋", "藕香榭",
          "栊翠庵", "暖香坞", "紫菱洲", "蓼风轩",
          "荣禧堂", "贾母上房", "王夫人正房", "凤姐院",
          "会芳园", "天香楼", "梨香院", "拢翠庵",
          "太虚幻境", "警幻仙宫",
          "京城", "金陵", "南京", "姑苏",
          "铁槛寺", "水月庵", "馒头庵", "清虚观",
          "葫芦庙", "十里街", "仁清巷")
        val titles = List("老太太", "太太", "奶奶", "姑娘", "小姐", "爷",
          "夫人", "姨娘", "丫鬟", "婆子", "嬷嬷",
          "老爷", "大爷", "二爷", "三爷",
          "王妃", "郡主", "诰命",
          "贵妃", "娘娘", "皇妃",
          "状元", "进士", "举人",
          "通判", "知府", "御史", "巡按",
          "国公", "侯爷", "世袭")
        val weapons = List("剑", "刀", "枪", "弓", "箭",
          "玉", "金锁", "通灵宝玉", "麒麟",
          "手帕", "扇子", "荷包", "香囊",
          "胭脂", "花粉", "首饰", "珠翠")
        (names, places, titles, weapons)

      case _ =>
        (List.empty[String], List.empty[String], List.empty[String], List.empty[String])
    }
  }
}

case class Novel(name: String, content: String, chapters: List[String])
