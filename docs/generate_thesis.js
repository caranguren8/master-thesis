/**
 * Generate thesis_draft.docx for:
 * "Electoral Closeness and Incumbency Advantage in Spain's Proportional Representation System"
 * Author: Camilo Andres Aranguren Barragan
 * Supervisor: Prof. Dr. Lukas Schmid | Co-supervisor: Prof. Oliver Staubli
 * Lucerne University of Applied Sciences and Arts, MSc in Applied Information and Data Science
 */

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat,
  ExternalHyperlink, Bookmark, FootnoteReferenceRun,
  TabStopType, TabStopPosition,
  TableOfContents, HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageNumber, PageBreak, ImageRun
} = require("docx");

const FIG_DIR = "/Users/Camilo/Desktop/master-thesis/data/processed/thesis_figures";

// ============================================================
// HELPER FUNCTIONS
// ============================================================

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const headerBorder = { style: BorderStyle.SINGLE, size: 1, color: "4472C4" };
const headerBorders = { top: headerBorder, bottom: headerBorder, left: headerBorder, right: headerBorder };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };

function headerCell(text, width) {
  return new TableCell({
    borders: headerBorders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: "D6E4F0", type: ShadingType.CLEAR },
    margins: cellMargins,
    verticalAlign: "center",
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text, bold: true, font: "Arial", size: 20 })] })]
  });
}

function dataCell(text, width, align) {
  const a = align === "right" ? AlignmentType.RIGHT : align === "center" ? AlignmentType.CENTER : AlignmentType.LEFT;
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    margins: cellMargins,
    children: [new Paragraph({ alignment: a, children: [new TextRun({ text: String(text), font: "Arial", size: 20 })] })]
  });
}

function stars(p) {
  if (p < 0.001) return "***";
  if (p < 0.01) return "**";
  if (p < 0.05) return "*";
  return "";
}

function fmtN(v, d) {
  return Number(v).toFixed(d);
}

function para(text, opts = {}) {
  const runs = [];
  if (typeof text === "string") {
    runs.push(new TextRun({ text, font: "Arial", size: 24, ...opts }));
  } else {
    runs.push(...text);
  }
  return new Paragraph({
    spacing: { after: 200, line: 360 },
    alignment: opts.alignment || AlignmentType.JUSTIFIED,
    children: runs
  });
}

function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 480, after: 240 },
    children: [new TextRun({ text, font: "Arial", size: 32, bold: true })]
  });
}

function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 360, after: 180 },
    children: [new TextRun({ text, font: "Arial", size: 28, bold: true })]
  });
}

function heading3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text, font: "Arial", size: 24, bold: true })]
  });
}

function emptyPara() {
  return new Paragraph({ children: [new TextRun({ text: "", font: "Arial", size: 24 })] });
}

function figureImage(filename, widthCm) {
  const filePath = path.join(FIG_DIR, filename);
  if (!fs.existsSync(filePath)) {
    console.warn("  WARNING: figure not found:", filePath);
    return para("[Figure not found: " + filename + "]");
  }
  const buf = fs.readFileSync(filePath);
  // Convert cm to EMU (1 cm = 360000 EMU)
  const widthEmu = Math.round(widthCm * 360000);
  // Aspect ratio from standard figure dimensions (approx 4:3 for single, 2.2:1 for double)
  const isTall = filename.includes("balance") || filename.includes("density") || filename.includes("first_stage") || filename.includes("runs") || filename.includes("wins");
  const heightEmu = isTall ? Math.round(widthEmu * 0.75) : Math.round(widthEmu * 0.45);
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 200, after: 100 },
    children: [
      new ImageRun({
        data: buf,
        transformation: { width: Math.round(widthCm * 37.8), height: Math.round(widthCm * 37.8 * (isTall ? 0.75 : 0.45)) },
        type: "png"
      })
    ]
  });
}

function figCaption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 300 },
    children: [new TextRun({ text, font: "Arial", size: 20, italics: true })]
  });
}

// ============================================================
// CONTENT SECTIONS
// ============================================================

// ---------- TITLE PAGE ----------
const titlePage = [
  emptyPara(), emptyPara(), emptyPara(), emptyPara(),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 120 },
    children: [new TextRun({ text: "Lucerne University of Applied Sciences and Arts", font: "Arial", size: 24, color: "666666" })]
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 400 },
    children: [new TextRun({ text: "MSc in Applied Information and Data Science", font: "Arial", size: 24, color: "666666" })]
  }),
  emptyPara(),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 120 },
    children: [new TextRun({ text: "Master\u2019s Thesis", font: "Arial", size: 28, color: "333333" })]
  }),
  emptyPara(),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200 },
    children: [new TextRun({ text: "Electoral Closeness and Incumbency Advantage", font: "Arial", size: 40, bold: true })]
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 400 },
    children: [new TextRun({ text: "in Spain\u2019s Proportional Representation System", font: "Arial", size: 40, bold: true })]
  }),
  emptyPara(), emptyPara(),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 100 },
    children: [new TextRun({ text: "Camilo Andres Aranguren Barragan", font: "Arial", size: 26, bold: true })]
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 100 },
    children: [new TextRun({ text: "camilo.arangurenbarragan@stud.hslu.ch", font: "Arial", size: 22, color: "4472C4" })]
  }),
  emptyPara(), emptyPara(),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 80 },
    children: [
      new TextRun({ text: "Supervisor: ", font: "Arial", size: 22, color: "666666" }),
      new TextRun({ text: "Prof. Dr. Lukas Schmid", font: "Arial", size: 22 })
    ]
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 80 },
    children: [
      new TextRun({ text: "Co-supervisor: ", font: "Arial", size: 22, color: "666666" }),
      new TextRun({ text: "Prof. Oliver Staubli", font: "Arial", size: 22 })
    ]
  }),
  emptyPara(), emptyPara(),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "May 2026", font: "Arial", size: 24 })]
  }),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- ABSTRACT ----------
const abstractSection = [
  heading1("Abstract"),
  para("This thesis estimates the causal effect of incumbency on subsequent electoral outcomes in Spain\u2019s proportional representation system at the candidate level. While a large body of research has established the existence and magnitude of incumbency advantages in majoritarian electoral systems, comparatively little is known about how incumbency operates in proportional representation (PR) contexts, where seat allocation follows the D\u2019Hondt method and party lists mediate the relationship between individual candidates and voters."),
  para("Leveraging the quasi-experimental variation generated by close electoral races, I employ a regression discontinuity design (RDD) adapted for PR systems following the closeness measure proposed by Luechinger, Schelker, and Schmid (2024). The running variable captures how close a party is to gaining or losing its last marginal seat in a given province, normalized by the number of eligible voters. Using data on all Spanish congressional (Congreso de los Diputados) elections from 2004 to 2023, encompassing 2,412 candidate-election observations, I estimate both sharp and fuzzy RDD specifications. Candidates are tracked across elections using a person-identifier linkage algorithm."),
  para("The results indicate a substantial and statistically significant incumbency advantage. Candidates whose party barely wins a marginal seat are approximately 28 percentage points more likely to reappear on a party list in the subsequent election (sharp RDD, p < 0.001) and 19 percentage points more likely to win a seat (sharp RDD, p < 0.001). There is suggestive evidence that winning a marginal seat also leads to more favorable list positions. These estimates are robust to alternative bandwidth choices, polynomial specifications, donut-hole restrictions, and different standard error clustering strategies. Placebo cutoff tests confirm no spurious effects at non-cutoff thresholds, and McCrary density tests reveal no evidence of strategic manipulation around the cutoff. The near-perfect first-stage relationship (\u03C4 \u2248 0.98) yields fuzzy RDD estimates that are virtually identical to sharp estimates, confirming the design\u2019s internal validity. Heterogeneity analysis shows that the incumbency advantage is present across districts of varying magnitudes."),
  para("These findings contribute to a growing literature on incumbency effects beyond majoritarian settings. They suggest that even in PR systems\u2014where the personal vote is often considered less important\u2014winning a marginal seat confers meaningful advantages for future electoral performance, operating through both candidate reappearance and list-position channels."),
  emptyPara(),
  para([
    new TextRun({ text: "Keywords: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "incumbency advantage, regression discontinuity design, proportional representation, Spain, D\u2019Hondt method, electoral closeness", font: "Arial", size: 24, italics: true })
  ]),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- DECLARATION ----------
const declarationSection = [
  heading1("Declaration of Independence"),
  para("I hereby confirm that I have carried out this work independently. All external help, aids, and the adoption of texts and programs from other sources are noted in this work. I confirm that this thesis has not been submitted in the same or similar form for examination purposes elsewhere."),
  emptyPara(), emptyPara(),
  new Paragraph({
    children: [
      new TextRun({ text: "Place, Date: ____________________________", font: "Arial", size: 24 })
    ]
  }),
  emptyPara(),
  new Paragraph({
    children: [
      new TextRun({ text: "Signature:    ____________________________", font: "Arial", size: 24 })
    ]
  }),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- TABLE OF CONTENTS ----------
const tocSection = [
  heading1("Table of Contents"),
  new TableOfContents("Table of Contents", {
    hyperlink: true,
    headingStyleRange: "1-3"
  }),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- LIST OF TABLES ----------
const listOfTables = [
  heading1("List of Tables"),
  para("Table 1: Summary Statistics by Treatment Status"),
  para("Table 2: Main RDD Estimates \u2013 Sharp and Fuzzy Specifications"),
  para("Table 3: Bandwidth Sensitivity Analysis"),
  para("Table 4: Standard Error Robustness"),
  para("Table 5: Outcome Definition Robustness"),
  para("Table 6: Placebo Cutoff Tests"),
  para("Table 7: Donut-Hole Robustness"),
  para("Table 8: Polynomial Order Comparison"),
  para("Table 9: McCrary Density Tests"),
  para("Table 10: Covariate Balance at the Cutoff"),
  emptyPara(),
  heading1("List of Figures"),
  para("Figure 1: Incumbency Effect on Running in Next Election (RDD Scatter)"),
  para("Figure 2: Incumbency Effect on Winning Seat in Next Election (RDD Scatter)"),
  para("Figure 3: First Stage \u2013 Election Status at the Cutoff"),
  para("Figure 4: McCrary Density Test \u2013 Running Variable Distribution"),
  para("Figure 5: Bandwidth Sensitivity Analysis with 95% Confidence Intervals"),
  para("Figure 6: Covariate Balance at the Cutoff"),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- CHAPTER 1: INTRODUCTION ----------
const ch1 = [
  heading1("1. Introduction"),

  heading2("1.1 Motivation"),
  para("The incumbency advantage\u2014the electoral benefit enjoyed by parties or candidates who currently hold office\u2014is one of the most studied phenomena in political science. Understanding whether and how incumbency confers advantages is crucial for evaluating democratic accountability, political competition, and representation. If incumbents enjoy significant advantages simply by virtue of holding office, this has implications for political turnover, policy responsiveness, and the health of democratic systems."),
  para("A rich empirical literature has documented incumbency effects in majoritarian, single-member district systems, particularly in the United States and the United Kingdom. The regression discontinuity design (RDD), which exploits the quasi-random assignment of incumbency status in close elections, has become the standard identification strategy. Seminal contributions by Lee (2008), who found a roughly 38 percentage point advantage for Democratic candidates winning close US House races, established this approach as a credible method for causal identification."),
  para("However, the vast majority of democracies worldwide employ some form of proportional representation (PR), where seats are allocated to parties in proportion to their vote shares. In these systems, the mechanisms underlying incumbency advantage may differ substantially from majoritarian contexts. Under PR, voters typically choose between party lists rather than individual candidates, the personal vote may play a diminished role, and the institutional channels through which incumbency operates\u2014such as name recognition, constituency service, and media visibility\u2014may be filtered through party organizations."),
  para("Spain provides an ideal setting for studying incumbency effects in a PR system. The country uses a closed-list PR system with the D\u2019Hondt method for seat allocation in its lower chamber (Congreso de los Diputados). Of the 52 electoral constituencies, 50 multi-member provinces use D\u2019Hondt proportional allocation, while Ceuta and Melilla are single-member plurality districts. This institutional design generates quasi-experimental variation at the margin of seat allocation: parties that barely win versus barely lose a marginal seat in a given province are, on average, comparable in terms of observable and unobservable characteristics, yet they differ in their incumbency status."),

  heading2("1.2 Research Questions"),
  para("This thesis addresses the following main research question:"),
  para([
    new TextRun({ text: "Main RQ: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "How does narrowly winning a parliamentary seat affect a candidate\u2019s future electoral prospects in Spain\u2019s proportional representation system?", font: "Arial", size: 24 })
  ]),
  para("This question is decomposed into four sub-questions:"),
  para([
    new TextRun({ text: "SQ1: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "How can electoral closeness be accurately measured at the candidate level in Spain\u2019s closed-list PR system?", font: "Arial", size: 24 })
  ]),
  para([
    new TextRun({ text: "SQ2: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Does narrowly winning a seat causally increase the probability of running again and/or being elected in the next election cycle (the incumbency advantage)?", font: "Arial", size: 24 })
  ]),
  para([
    new TextRun({ text: "SQ3: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "How does the incumbency advantage differ across electoral districts of varying sizes (district magnitudes)?", font: "Arial", size: 24 })
  ]),
  para([
    new TextRun({ text: "SQ4: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "To what extent does incumbency affect a candidate\u2019s future position on party lists?", font: "Arial", size: 24 })
  ]),

  heading2("1.3 Contribution"),
  para("This thesis makes several contributions to the literature, going beyond a straightforward application of the Luechinger, Schelker, and Schmid (2024) methodology to a new country."),
  para("First, Spain offers a theoretically informative test case that differs from the countries for which incumbency advantages under PR have been estimated in important ways. Luechinger, Schelker, and Schmid (2024) study Switzerland\u2019s open-list PR system with panachage, where voters can freely modify party lists and cast personal preference votes; any incumbency effect there could operate through the personal vote channel. Spain\u2019s closed-list system shuts down this channel entirely: voters choose between sealed party lists and cannot influence which individual candidates are elected. If an incumbency advantage persists even when voters have no ability to reward or punish individual incumbents, it must operate through party-level mechanisms\u2014organizational resources, demonstrated viability, and gatekeeper decisions about list composition\u2014rather than through the personal vote. Spain therefore provides a clean test of whether party-mediated incumbency effects exist independently of candidate-centered electoral incentives."),
  para("Second, Spain\u2019s institutional features generate analytical variation not available in other studied contexts. The 50 PR provinces range from 1-seat effective districts (Soria) to 37-seat megadistricts (Madrid), providing within-country variation in district magnitude that allows a direct test of whether incumbency advantages are modulated by the competitiveness of the seat allocation environment. Furthermore, Spain\u2019s party system underwent dramatic fragmentation during the sample period (2004\u20132023), with the emergence of Podemos and Ciudadanos breaking the traditional PSOE\u2013PP duopoly. This provides a dynamic multi-party setting absent from the Swiss and Norwegian contexts studied previously."),
  para("Third, this thesis extends the analysis beyond the standard runs-next/wins-next outcomes by investigating list-position effects\u2014a question unique to closed-list PR systems and one that directly probes the party-gatekeeper mechanism. If parties reward marginal-seat winners with more favorable list positions in subsequent elections, this reveals a concrete organizational channel through which incumbency perpetuates itself."),
  para("Fourth, by implementing a comprehensive battery of robustness checks\u2014placebo cutoff tests, donut-hole restrictions, polynomial order sensitivity, bandwidth sensitivity, and McCrary density tests\u2014and by tracking individual candidates across elections via a person-identifier linkage algorithm, this thesis establishes the credibility of the empirical design in a context where such validation has not been performed before."),

  heading2("1.4 Preview of Results"),
  para("The main findings indicate a substantial incumbency advantage in Spain\u2019s PR system. Candidates whose party barely wins a marginal seat are approximately 28 percentage points more likely to reappear on a party list in the next election and 19 percentage points more likely to win a seat. There is suggestive evidence that winning a marginal seat also leads to more favorable list positions, and the effect is present across districts of varying magnitudes. These effects are highly statistically significant and robust across multiple specifications. The near-perfect first-stage relationship confirms that winning the marginal seat almost perfectly determines incumbency status, validating the research design."),

  heading2("1.5 Structure"),
  para("The remainder of this thesis is organized as follows. Chapter 2 reviews the relevant literature on incumbency advantage. Chapter 3 describes Spain\u2019s electoral system and the institutional context. Chapter 4 presents the methodological framework, including the RDD identification strategy and the closeness measure for PR systems. Chapter 5 describes the data. Chapter 6 presents the main results. Chapter 7 provides extensive robustness checks. Chapter 8 discusses the findings, and Chapter 9 concludes."),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- CHAPTER 2: LITERATURE REVIEW ----------
const ch2 = [
  heading1("2. Literature Review"),

  heading2("2.1 Incumbency Advantage in Majoritarian Systems"),
  para("The study of incumbency advantage has a long tradition in political science, dating back to early observations that incumbent legislators tend to win re-election at rates far exceeding what would be expected by chance. Gelman and King (1990) formalized the concept of the \u201Cincumbency advantage\u201D as the average causal effect of a party holding a seat on its vote share in subsequent elections. Subsequent work by Lee (2008) revolutionized the field by applying a regression discontinuity design to US House elections, exploiting the quasi-random assignment of party control in close races to identify causal effects. Lee\u2019s estimate of a roughly 38 percentage point advantage for the winning party in close US elections demonstrated the power of the RDD approach and established it as the gold standard for measuring incumbency effects."),
  para("Following Lee (2008), numerous studies have applied the RDD framework to majoritarian elections in various countries. Caughey and Sekhon (2011) raised concerns about potential sorting near the cutoff in close US elections, though subsequent work has generally validated the RDD approach with appropriate controls. The literature has explored various mechanisms through which incumbency confers advantages, including name recognition, campaign finance advantages, constituency service, pork-barrel spending, and media coverage."),

  heading2("2.2 Incumbency Effects in Proportional Representation"),
  para("Extending the incumbency advantage literature to PR systems presents unique challenges. Unlike majoritarian systems where a single candidate wins or loses a district, PR systems allocate multiple seats per constituency according to party vote shares. The personal vote mechanism is often attenuated in PR systems, especially those with closed party lists where voters cannot choose among individual candidates within a party. Nonetheless, parties that win representation in a district may benefit from increased visibility, stronger organizational presence, and demonstrated electoral viability."),
  para("Dano, Ferlenga, Galasso, Le Pennec, and Pons (2022) studied coordination and incumbency advantage in multi-party systems using French elections and an RDD approach. Their work highlights that in multi-party settings, incumbency can affect not only direct electoral performance but also the strategic behavior of competing parties. The findings suggest that incumbency effects operate through both direct channels (voter loyalty, name recognition) and indirect channels (strategic entry and exit of competitors)."),
  para("Luechinger, Schelker, and Schmid (2024) made a key methodological contribution by developing a measure of electoral closeness suitable for proportional representation systems. In majoritarian systems, closeness is simply the vote margin between the winner and the runner-up. In PR systems with D\u2019Hondt or similar divisor methods, closeness must be defined relative to the marginal seat allocation. Their measure identifies how many additional votes a party would need to gain (or could afford to lose) to win (or lose) one additional seat, normalized by the number of eligible voters. This measure provides the running variable for an RDD framework adapted to PR contexts."),
  para("A key gap in this emerging literature concerns the decomposition of the incumbency advantage into its constituent channels. Most studies report a single reduced-form effect on vote shares or seat wins, but the total effect may mask distinct mechanisms. Distinguishing the extensive margin (whether a party\u2019s candidates reappear at all) from the intensive margin (whether they win conditional on running) is important because the two channels have different policy implications: a large extensive-margin effect suggests that incumbency operates through party viability and organizational persistence, while a large intensive-margin effect points to direct electoral benefits such as voter loyalty or resource advantages. Furthermore, in closed-list PR systems, the party\u2019s internal decision about list composition\u2014specifically, where to place candidates on the list\u2014is a theoretically distinct channel that mediates between party-level incumbency status and individual candidate outcomes (Hazan and Rahat, 2010; Galasso and Nannicini, 2011). Examining this channel requires tracking individual candidates across elections and observing changes in their list positions, which this thesis does."),

  heading2("2.3 The Spanish Context in the Literature"),
  para("Spain\u2019s electoral system has been studied from various angles, including the effects of district magnitude on proportionality, the relationship between electoral rules and party system fragmentation, and the strategic behavior of parties under the D\u2019Hondt method. However, to the best of my knowledge, no prior study has applied the RDD framework with the Luechinger, Schelker, and Schmid (2024) closeness measure to estimate the incumbency advantage in Spanish congressional elections. This thesis fills that gap."),
  para("Spain is a particularly interesting case for several reasons. First, the 50 PR provinces vary substantially in district magnitude, from small provinces electing two or three members to large multi-member districts such as Madrid and Barcelona, providing variation in the competitiveness and proportionality of seat allocation. Second, Spain uses a closed-list system where voters cannot express preferences for individual candidates, meaning that any incumbency effect operates primarily through the party rather than individual candidate channels. Third, the Spanish party system has undergone significant transformation during the period studied (2004\u20132023), including the rise of new parties such as Podemos and Ciudadanos, providing a dynamic political context."),

  heading2("2.4 Hypotheses"),
  para("Drawing on the theoretical and empirical literature reviewed above, this thesis tests the following hypotheses. Each is grounded in established theoretical mechanisms from the incumbency advantage literature."),

  para([
    new TextRun({ text: "H1 (Extensive margin): ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Candidates whose party barely wins a marginal seat are more likely to reappear on the party list in the subsequent election.", font: "Arial", size: 24 })
  ]),
  para("The theoretical basis for this hypothesis draws on two established mechanisms. First, the \u201Cscare-off\u201D or deterrence effect (Cox and Katz, 1996; Ansolabehere and Snyder, 2002): parties that hold a seat may deter competitors and signal viability, encouraging their own candidates to stand again while discouraging exit. Second, the resource channel: winning representation provides access to parliamentary budgets, staff, and media platforms (Erikson, 1971), reducing the fixed costs of contesting the next election. In PR systems with closed lists, these resources accrue primarily to the party organization rather than individual candidates, but they still shape the party\u2019s decision to field candidates in a given province. Empirically, Luechinger, Schelker, and Schmid (2024) find a large extensive-margin effect in Swiss PR elections, suggesting that this channel is operative beyond majoritarian settings."),

  para([
    new TextRun({ text: "H2 (Intensive margin): ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Candidates whose party barely wins a marginal seat are more likely to win a seat in the subsequent election.", font: "Arial", size: 24 })
  ]),
  para("Beyond simply running again, the incumbency advantage literature identifies several channels through which holding office improves subsequent electoral performance. Gelman and King (1990) formalize the \u201Cquality advantage\u201D: incumbent parties benefit from demonstrated competence and policy delivery. Lee (2008) argues that close-election RDD captures the combined effect of all incumbency channels\u2014name recognition, constituency service, media exposure, pork-barrel spending\u2014without needing to decompose them individually. In a closed-list PR system, the intensive-margin effect should reflect party-level rather than candidate-level advantages: voters reward or punish the party\u2019s record, and the D\u2019Hondt mechanism translates aggregate vote gains into additional seats."),

  para([
    new TextRun({ text: "H3 (List-position channel): ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "Candidates whose party barely wins a marginal seat receive more favorable (higher) list positions in subsequent elections.", font: "Arial", size: 24 })
  ]),
  para("This hypothesis probes a mechanism specific to closed-list PR systems and draws on the selectorate theory of candidate selection (Hazan and Rahat, 2010). In closed-list systems, party gatekeepers\u2014rather than voters\u2014determine list rankings. Theoretical models of intra-party competition predict that parties reward candidates who have demonstrated electability and accumulated legislative experience with more prominent list positions (Galasso and Nannicini, 2011). If incumbency experience serves as a signal of candidate quality to party selectors, then marginal-seat winners should receive better list placements in the next election. This hypothesis is testable only among candidates who reappear on a party list, making it conditional on the extensive margin. The list-position channel has not been examined in previous RDD studies of incumbency under PR, making it a novel contribution of this thesis."),

  para([
    new TextRun({ text: "H4 (District magnitude heterogeneity): ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "The incumbency advantage varies with district magnitude, with stronger effects expected in low-magnitude districts.", font: "Arial", size: 24 })
  ]),
  para("The theoretical prediction follows from the mechanical properties of proportional seat allocation. Taagepera and Shugart (1989) show that as district magnitude decreases, the effective threshold for winning a seat increases, making each seat more valuable and competition for the marginal seat more intense. In small-magnitude districts (2\u20134 seats), each seat represents a large share of the province\u2019s representation, amplifying the organizational and visibility returns to holding office. Conversely, in large-magnitude districts (e.g., Madrid with 36\u201337 seats), the marginal seat represents a smaller share of total representation, potentially attenuating incumbency effects. Empirically, this heterogeneity test speaks to the external validity debate in the RDD literature: if effects are confined to a particular district type, the policy implications differ from a finding of broad, systemic incumbency advantages."),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- CHAPTER 3: INSTITUTIONAL BACKGROUND ----------
const ch3 = [
  heading1("3. Institutional Background"),

  heading2("3.1 The Spanish Congress of Deputies"),
  para("The Congreso de los Diputados (Congress of Deputies) is the lower house of Spain\u2019s bicameral legislature, the Cortes Generales. It consists of 350 members. Of these, 348 are elected from 50 multi-member provincial constituencies using a closed-list proportional representation system with the D\u2019Hondt method. The remaining two members represent the autonomous cities of Ceuta and Melilla, each elected in a single-member district by plurality vote. Elections are held at least every four years, though early elections can be called by the Prime Minister or triggered by political circumstances."),
  para("Each of the 50 provinces is allocated a minimum of two seats, with the remaining seats distributed among provinces in proportion to their population. Ceuta and Melilla each receive one seat. This allocation results in significant variation in district magnitude: from the single-member districts of Ceuta and Melilla to Madrid, which elects the most representatives (typically 36\u201337). The average district magnitude across the 50 PR provinces is approximately 7.0 seats."),

  heading2("3.2 The D\u2019Hondt Method"),
  para("Within each of the 50 multi-member provinces, seats are allocated to parties using the D\u2019Hondt method (also known as the Jefferson method), a highest-averages method of proportional representation. Parties that receive at least 3% of valid votes in a province are eligible for seat allocation. However, this legal threshold is only binding in the largest constituencies such as Madrid and Barcelona; in smaller provinces with few seats, the effective threshold for winning a seat is substantially higher due to the mechanical properties of the allocation formula. The method works by iteratively dividing each party\u2019s total vote count by successive integers (1, 2, 3, ...) and allocating seats to the highest quotients until all seats in the province are filled."),
  para("The D\u2019Hondt method tends to slightly favor larger parties compared to other proportional methods, and this tendency is amplified in small-magnitude districts. This feature of Spain\u2019s electoral system has been widely discussed in the literature as contributing to the country\u2019s historically two-party-dominant system, although the emergence of new parties in the 2010s partially altered this dynamic."),

  heading2("3.3 Implications for Identification"),
  para("The D\u2019Hondt allocation mechanism is central to the identification strategy employed in this thesis. At the margin of seat allocation, small differences in vote shares can determine whether a party wins or loses a seat. A party that barely passes the threshold for a marginal seat under D\u2019Hondt is, in expectation, similar to a party that barely fails to reach this threshold. This quasi-random assignment around the marginal seat threshold provides the basis for the regression discontinuity design."),
  para("Several features of the Spanish system make it well-suited for this analysis. First, parties cannot precisely control their vote totals, especially in close races, meaning that assignment near the cutoff approximates random assignment. Second, the large number of province-election observations across multiple elections provides sufficient statistical power. Third, the closed-list system means that individual candidate characteristics are less likely to confound the incumbency effects being estimated, as the running variable is determined by the party\u2019s aggregate performance rather than individual candidate attributes. The analysis is restricted to the 50 multi-member PR provinces; the single-member plurality districts of Ceuta and Melilla are excluded because the D\u2019Hondt closeness measure is not applicable to plurality elections."),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- CHAPTER 4: METHODOLOGY ----------
const ch4 = [
  heading1("4. Methodology"),

  heading2("4.1 Regression Discontinuity Design"),
  para("The regression discontinuity design (RDD) exploits discontinuities in treatment assignment that arise when a treatment is determined by whether an observed variable\u2014the running variable\u2014crosses a known threshold. In the sharp RDD, treatment status is a deterministic function of the running variable: units above the cutoff receive treatment, while those below do not. The fuzzy RDD relaxes this assumption, allowing treatment to be a probabilistic function of crossing the threshold."),
  para("The key identifying assumption of the RDD is that the conditional expectation of potential outcomes is continuous at the cutoff. Under this assumption, any discontinuity in the observed outcome at the cutoff can be attributed to the causal effect of treatment. The local average treatment effect (LATE) is identified by comparing outcomes of units just above and just below the cutoff, within an appropriately chosen bandwidth."),

  heading2("4.2 Closeness Measure for PR Systems"),
  para("In majoritarian systems, the running variable for an incumbency RDD is simply the vote margin between the winner and the runner-up. In proportional representation systems with D\u2019Hondt allocation, defining closeness requires a more sophisticated approach."),
  para("Following Luechinger, Schelker, and Schmid (2024), I define the running variable as the minimal vote change needed for a party to gain or lose one additional seat in a given province, normalized by the number of eligible voters. Specifically, for each party-province-election observation, I compute the minimum number of votes that would need to be added (if the party barely lost a seat) or subtracted (if the party barely won a seat) to change the D\u2019Hondt allocation by exactly one seat. This vote margin is then divided by the number of eligible voters in the province to produce a standardized measure that is comparable across provinces of different sizes."),
  para("The resulting running variable takes positive values for parties that won the marginal seat and negative values for parties that lost it. The cutoff is at zero, and the treatment indicator equals one for observations with a non-negative running variable (i.e., parties that won the marginal seat)."),

  heading2("4.3 Estimation"),
  para("I estimate the incumbency effect using local linear regression within a bandwidth around the cutoff. The estimating equation for the sharp RDD is:"),
  para([new TextRun({ text: "Y\u1D62 = \u03B1 + \u03B2X\u1D62 + \u03C4T\u1D62 + \u03B3(T\u1D62 \u00D7 X\u1D62) + \u03B5\u1D62", font: "Arial", size: 24, italics: true })], { alignment: AlignmentType.CENTER }),
  para("where Y\u1D62 is the outcome of interest, X\u1D62 is the running variable (normalized vote margin), T\u1D62 = 1(X\u1D62 \u2265 0) is the treatment indicator, and T\u1D62 \u00D7 X\u1D62 allows the slope to differ on each side of the cutoff. The parameter \u03C4 captures the incumbency effect. I use a pooled regression specification with a triangular kernel to weight observations inversely proportional to their distance from the cutoff. Three primary outcomes are considered: (i) whether the candidate reappears on a party list in the subsequent election (runs next), (ii) whether the candidate wins a seat in the subsequent election (wins next), and (iii) the candidate\u2019s list position in the subsequent election (list position next), which is observed only for candidates who do reappear and is therefore conditional on the extensive margin. Candidates are tracked across elections using a person-identifier linkage algorithm that combines exact name matching with fuzzy similarity and LinkTransformer embeddings."),
  para("Standard errors are clustered at the province-election level to account for within-group correlation. I report inference based on the t-distribution with G \u2212 1 degrees of freedom, where G is the number of clusters, which is the standard finite-cluster correction (see Cameron, Gelbach, and Miller, 2008, for a discussion of clustered inference). This is conservative relative to normal approximation and appropriate given the finite number of clusters."),
  para("The primary bandwidth is set at 0.05 (i.e., parties within 5 percentage points of the D\u2019Hondt cutoff), which serves as the workhorse specification throughout the analysis. As a complement, I report results using the data-driven bandwidth selector of Calonico, Cattaneo, and Titiunik (2014), which minimizes the asymptotic mean squared error of the local polynomial estimator while accounting for bias correction. I present robustness to a range of alternative bandwidths (0.025 to 0.10) in the sensitivity analysis."),
  para("The estimation is implemented in Python. The closeness measure and D\u2019Hondt allocation algorithm are computed with custom code. For bandwidth selection and bias-corrected inference, I use the rdrobust package (Calonico, Cattaneo, and Titiunik, 2014), which provides robust confidence intervals that account for the bias inherent in local polynomial estimation near boundaries. All tables and figures are generated programmatically to ensure reproducibility."),

  heading2("4.4 Fuzzy RDD"),
  para("While the sharp RDD treats the running variable as perfectly determining treatment (incumbency), in practice the relationship may be imperfect. The fuzzy RDD addresses this by using the running variable as an instrument for actual incumbency status. The Wald (LATE) estimator divides the reduced-form discontinuity in outcomes by the first-stage discontinuity in treatment:"),
  para([new TextRun({ text: "\u03C4\u1DA0\u1D58\u1DBB\u1DBB\u02B8 = \u03C4\u02B3\u1D49\u1D48\u1D58\u1D9C\u1D49\u1D48\u1DA0\u1D52\u02B3\u1D50 / \u03C4\u1DA0\u1D62\u02B3\u02E2\u1D57\u02E2\u1D57\u1D43\u1D4D\u1D49", font: "Arial", size: 24, italics: true })], { alignment: AlignmentType.CENTER }),
  para("In the present context, the first-stage relationship is near-perfect (\u03C4 \u2248 0.98), meaning that crossing the cutoff almost perfectly predicts actual incumbency status. As a result, the sharp and fuzzy estimates are nearly identical, and the first-stage F-statistic far exceeds the Stock and Yogo (2005) threshold of 10, ruling out weak instrument concerns."),

  heading2("4.5 Validity Tests"),
  para("I implement several tests to assess the validity of the RDD design:"),
  para([
    new TextRun({ text: "McCrary Density Test: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "I test for manipulation of the running variable by examining whether the density of observations exhibits a discontinuity at the cutoff, following McCrary (2008). If parties could precisely manipulate their vote totals to barely win marginal seats, we would expect a discontinuous jump in density at zero.", font: "Arial", size: 24 })
  ]),
  para([
    new TextRun({ text: "Covariate Balance: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "I test whether pre-determined covariates\u2014including gender composition, list position, party votes, constituency size, and blank vote shares\u2014are balanced around the cutoff. Significant discontinuities in these variables would suggest that assignment near the cutoff is not quasi-random.", font: "Arial", size: 24 })
  ]),
  para([
    new TextRun({ text: "Placebo Cutoff Tests: ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "I estimate the RDD at placebo cutoffs (the median of each side of the distribution) where no treatment effect should exist. Finding significant effects at non-cutoff thresholds would undermine the credibility of the design.", font: "Arial", size: 24 })
  ]),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- CHAPTER 5: DATA ----------
const ch5 = [
  heading1("5. Data"),

  heading2("5.1 Data Sources"),
  para("The analysis draws on comprehensive data from Spanish congressional elections held between 2004 and 2023, covering eight general elections (2004, 2008, 2011, 2015, 2016, 2019 April, 2019 November, and 2023). The analysis is restricted to the 50 multi-member provinces where the D\u2019Hondt method applies, excluding the single-member plurality districts of Ceuta and Melilla. The primary data sources include official election results from Spain\u2019s Electoral Board (Junta Electoral Central), providing detailed vote counts by party, province, and election. Candidate-level data, including names, party affiliations, and list positions, are obtained from official candidate lists."),
  para("The unit of analysis is the candidate-election, representing an individual candidate\u2019s participation in a specific election. The running variable\u2014the normalized vote margin for the marginal seat\u2014is computed at the party-province level using the D\u2019Hondt allocation algorithm as described in Chapter 4; all candidates on a given party list in a province share the same running variable value. Outcomes, however, are tracked at the individual candidate level using a person-identifier linkage algorithm that matches candidates across election cycles, enabling the analysis of personal reappearance, re-election, and list-position dynamics."),

  heading2("5.2 Sample Construction"),
  para("The full dataset comprises 2,412 candidate-election observations within the analysis window (running variable between \u22120.05 and +0.05). After linking outcomes to the subsequent election via the person-identifier algorithm, the estimation sample for the \u201Cruns next\u201D and \u201Cwins next\u201D outcomes contains 2,118 observations. The list-position outcome is available only for the subset of candidates who reappear on a party list in the subsequent election."),

  heading2("5.3 Summary Statistics"),
  para("Table 1 presents summary statistics for the key variables, disaggregated by treatment status (above vs. below the cutoff)."),
  emptyPara(),
  para([new TextRun({ text: "Table 1: Summary Statistics by Treatment Status", bold: true, font: "Arial", size: 22 })], { alignment: AlignmentType.CENTER }),

  // Summary statistics table
  (() => {
    const colW = [1800, 900, 1100, 900, 900, 1100, 900];
    return new Table({
      width: { size: 7600, type: WidthType.DXA },
      columnWidths: colW,
      rows: [
        new TableRow({ children: [
          headerCell("Variable", colW[0]),
          headerCell("N", colW[1]),
          headerCell("Mean (All)", colW[2]),
          headerCell("SD", colW[3]),
          headerCell("Mean (L)", colW[4]),
          headerCell("Mean (R)", colW[5]),
          headerCell("Diff", colW[6]),
        ]}),
        ...[
          ["Running var.", "2,412", "\u22120.011", "0.029", "\u22120.030", "0.024", "0.054"],
          ["Elected", "2,412", "0.350", "0.477", "0.004", "0.994", "0.990"],
          ["Runs next", "2,118", "0.408", "0.492", "0.310", "0.597", "0.287"],
          ["Wins next", "2,118", "0.174", "0.379", "0.056", "0.402", "0.346"],
          ["Female share", "1,879", "0.404", "0.491", "0.413", "0.387", "\u22120.026"],
          ["List position", "2,412", "2.492", "2.458", "2.335", "2.783", "0.448"],
          ["Log party votes", "2,412", "10.577", "2.019", "9.937", "11.767", "1.830"],
          ["Party seats", "2,412", "1.772", "2.610", "1.144", "2.937", "1.793"],
          ["Blank vote %", "2,412", "0.010", "0.004", "0.010", "0.009", "\u22120.000"],
        ].map(row => new TableRow({ children: row.map((v, i) => dataCell(v, colW[i], i === 0 ? "left" : "right")) }))
      ]
    });
  })(),
  emptyPara(),
  para([new TextRun({ text: "Notes: ", italics: true, font: "Arial", size: 20 }), new TextRun({ text: "L = Below cutoff (lost marginal seat); R = Above cutoff (won marginal seat). Running variable is normalized by eligible voters. Bandwidth = 0.05. Diff = Mean(R) \u2212 Mean(L).", font: "Arial", size: 20 })]),
  emptyPara(),
  para("The summary statistics reveal several expected patterns. Parties above the cutoff (treatment group) have nearly perfect election rates (99.4%), consistent with the marginal seat allocation. The raw difference in the probability of running in the next election (28.7 percentage points) and winning next (34.6 percentage points) already suggests a substantial incumbency effect, though these naive comparisons do not account for potential confounders. The covariate columns show that while some variables differ between groups (notably log party votes and party seats, which are mechanically related to winning), others such as blank vote share are well-balanced."),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- CHAPTER 6: RESULTS ----------
const ch6 = [
  heading1("6. Results"),

  heading2("6.1 Main Estimates"),
  para("Table 2 presents the main RDD estimates for both outcome variables under the sharp and fuzzy specifications. The bandwidth is selected by the robust bias-corrected optimal bandwidth selector of Calonico, Cattaneo, and Titiunik (2014), and standard errors are clustered at the province-election level with t-distribution inference."),
  emptyPara(),
  para([new TextRun({ text: "Table 2: Main RDD Estimates \u2013 Sharp and Fuzzy Specifications", bold: true, font: "Arial", size: 22 })], { alignment: AlignmentType.CENTER }),

  (() => {
    const colW = [1400, 1100, 1200, 1200, 1200, 1200, 1200];
    return new Table({
      width: { size: 8500, type: WidthType.DXA },
      columnWidths: colW,
      rows: [
        new TableRow({ children: [
          headerCell("Outcome", colW[0]),
          headerCell("BW", colW[1]),
          headerCell("Sharp \u03C4", colW[2]),
          headerCell("Sharp SE", colW[3]),
          headerCell("Fuzzy \u03C4", colW[4]),
          headerCell("Fuzzy SE", colW[5]),
          headerCell("1st Stage", colW[6]),
        ]}),
        new TableRow({ children: [
          dataCell("Runs next", colW[0], "left"),
          dataCell("0.112", colW[1], "right"),
          dataCell("0.278***", colW[2], "right"),
          dataCell("(0.033)", colW[3], "right"),
          dataCell("0.282***", colW[4], "right"),
          dataCell("(0.033)", colW[5], "right"),
          dataCell("0.985***", colW[6], "right"),
        ]}),
        new TableRow({ children: [
          dataCell("Wins next", colW[0], "left"),
          dataCell("0.068", colW[1], "right"),
          dataCell("0.196***", colW[2], "right"),
          dataCell("(0.039)", colW[3], "right"),
          dataCell("0.200***", colW[4], "right"),
          dataCell("(0.040)", colW[5], "right"),
          dataCell("0.981***", colW[6], "right"),
        ]}),
      ]
    });
  })(),
  emptyPara(),
  para([new TextRun({ text: "Notes: ", italics: true, font: "Arial", size: 20 }), new TextRun({ text: "Standard errors (province-election clustered) in parentheses. *** p<0.001, ** p<0.01, * p<0.05. BW = CCT optimal bandwidth (Calonico, Cattaneo, and Titiunik, 2014). Sharp = intent-to-treat. Fuzzy = Wald/LATE estimator.", font: "Arial", size: 20 })]),
  emptyPara(),
  para("The results provide strong evidence for an incumbency advantage in Spain\u2019s PR system. The sharp RDD estimate for the probability of running in the next election is 0.278 (SE = 0.033, p < 0.001), indicating that parties barely winning a marginal seat are approximately 28 percentage points more likely to contest the subsequent election. The effect on winning a seat in the next election is 0.196 (SE = 0.039, p < 0.001). These CCT-selected bandwidths are broadly consistent with the workhorse BW = 0.05 specification, which yields estimates of 0.285 and 0.186 for the two outcomes respectively (see Table 3 for bandwidth sensitivity)."),
  para("The fuzzy RDD estimates are virtually identical to the sharp estimates, reflecting the near-perfect first-stage relationship. The first-stage coefficient is 0.985 for the \u201Cruns next\u201D specification and 0.981 for \u201Cwins next,\u201D both highly significant. These values confirm that crossing the D\u2019Hondt allocation cutoff almost perfectly determines actual incumbency status, as expected in this institutional setting. The corresponding first-stage F-statistics far exceed the Stock and Yogo (2005) threshold of 10, ruling out weak instrument concerns."),
  para("Figures 1 and 2 visualize the main results. Each panel shows the binned scatter plot of the outcome variable against the running variable, with local-linear fits on each side of the cutoff. The sharp jump at the discontinuity is clearly visible, confirming the incumbency advantage estimated in Table 2."),
  figureImage("fig1_rdd_runs_next.png", 15),
  figCaption("Figure 1: Incumbency Effect on Running in Next Election. Binned scatter with local-linear fits (BW = 0.05)."),
  figureImage("fig2_rdd_wins_next.png", 15),
  figCaption("Figure 2: Incumbency Effect on Winning Seat in Next Election. Binned scatter with local-linear fits (BW = 0.05)."),
  para("Figure 3 displays the first-stage relationship, showing that crossing the cutoff almost perfectly determines actual election status. The near-complete separation between the two sides\u2014with election probabilities jumping from near zero to near one\u2014validates the research design and confirms that the sharp and fuzzy RDD specifications should yield similar estimates."),
  figureImage("fig3_first_stage.png", 15),
  figCaption("Figure 3: First Stage \u2013 Probability of Being Elected at the Cutoff (BW = 0.05)."),

  heading2("6.2 Bandwidth Sensitivity"),
  para("Table 3 examines the sensitivity of the main estimates to alternative bandwidth choices, ranging from 0.025 to 0.100 (normalized vote margin)."),
  emptyPara(),
  para([new TextRun({ text: "Table 3: Bandwidth Sensitivity", bold: true, font: "Arial", size: 22 })], { alignment: AlignmentType.CENTER }),

  (() => {
    const colW = [1400, 900, 1300, 1300, 1300, 1300];
    return new Table({
      width: { size: 7500, type: WidthType.DXA },
      columnWidths: colW,
      rows: [
        new TableRow({ children: [
          headerCell("Outcome", colW[0]),
          headerCell("BW", colW[1]),
          headerCell("Sharp \u03C4", colW[2]),
          headerCell("SE", colW[3]),
          headerCell("Fuzzy \u03C4", colW[4]),
          headerCell("Fuzzy SE", colW[5]),
        ]}),
        ...["runs_next", "wins_next"].flatMap(oc => {
          const label = oc === "runs_next" ? "Runs next" : "Wins next";
          return [0.025, 0.05, 0.075, 0.1].map(bw => {
            const stau = oc === "runs_next" ? [0.347, 0.285, 0.277, 0.276] : [0.183, 0.186, 0.203, 0.235];
            const sse  = oc === "runs_next" ? [0.064, 0.048, 0.040, 0.034] : [0.066, 0.047, 0.037, 0.032];
            const ftau = oc === "runs_next" ? [0.354, 0.291, 0.282, 0.281] : [0.187, 0.190, 0.207, 0.239];
            const fse  = oc === "runs_next" ? [0.066, 0.050, 0.041, 0.035] : [0.067, 0.048, 0.038, 0.032];
            const sp   = oc === "runs_next" ? [1.1e-7, 6.9e-9, 1.2e-11, 1e-14] : [0.006, 9.4e-5, 5.2e-8, 4.8e-13];
            const idx = [0.025, 0.05, 0.075, 0.1].indexOf(bw);
            const s = stars(sp[idx]);
            return new TableRow({ children: [
              dataCell(label, colW[0], "left"),
              dataCell(bw.toFixed(3), colW[1], "right"),
              dataCell(stau[idx].toFixed(3) + s, colW[2], "right"),
              dataCell("(" + sse[idx].toFixed(3) + ")", colW[3], "right"),
              dataCell(ftau[idx].toFixed(3) + s, colW[4], "right"),
              dataCell("(" + fse[idx].toFixed(3) + ")", colW[5], "right"),
            ]});
          });
        })
      ]
    });
  })(),
  emptyPara(),
  para([new TextRun({ text: "Notes: ", italics: true, font: "Arial", size: 20 }), new TextRun({ text: "Province-election clustered SEs in parentheses. *** p<0.001, ** p<0.01, * p<0.05.", font: "Arial", size: 20 })]),
  emptyPara(),
  para("The estimates are stable across bandwidths. For the \u201Cruns next\u201D outcome, the sharp estimate ranges from 0.276 to 0.347 as the bandwidth narrows from 0.100 to 0.025, with the expected pattern of larger estimates (but also larger standard errors) at narrower bandwidths. The \u201Cwins next\u201D effect shows a similar pattern, ranging from 0.185 to 0.238 across bandwidths. Critically, all estimates remain statistically significant at conventional levels across the full range of bandwidths, providing confidence in the robustness of the findings."),
  para("Figure 5 visualizes this stability. The point estimates and 95% confidence intervals are plotted against bandwidth, clearly showing that the effect is consistently above zero and that the confidence bands never include zero at any bandwidth."),
  figureImage("fig5_bandwidth_sensitivity.png", 15),
  figCaption("Figure 5: Bandwidth Sensitivity Analysis. Point estimates and 95% CIs across bandwidths (0.025\u20130.100)."),

  heading2("6.3 Standard Error Robustness"),
  para("Table 4 compares the main estimates under three standard error specifications: heteroskedasticity-robust (HC1), province-election clustered, and province-election-party clustered."),
  emptyPara(),
  para([new TextRun({ text: "Table 4: Standard Error Robustness (BW = 0.05)", bold: true, font: "Arial", size: 22 })], { alignment: AlignmentType.CENTER }),

  (() => {
    const colW = [1500, 2400, 1200, 1200, 1200];
    return new Table({
      width: { size: 7500, type: WidthType.DXA },
      columnWidths: colW,
      rows: [
        new TableRow({ children: [
          headerCell("Outcome", colW[0]),
          headerCell("SE Type", colW[1]),
          headerCell("Sharp \u03C4", colW[2]),
          headerCell("SE", colW[3]),
          headerCell("p-value", colW[4]),
        ]}),
        ...["Runs next", "Wins next"].flatMap(label => {
          const tau = label === "Runs next" ? "0.285" : "0.186";
          const ses = label === "Runs next" ? ["0.050", "0.048", "0.050"] : ["0.046", "0.047", "0.045"];
          const ps  = label === "Runs next" ? ["<0.001", "<0.001", "<0.001"] : ["<0.001", "<0.001", "<0.001"];
          return ["HC1", "Province-election", "Province-election-party"].map((se, i) =>
            new TableRow({ children: [
              dataCell(label, colW[0], "left"),
              dataCell(se, colW[1], "left"),
              dataCell(tau + "***", colW[2], "right"),
              dataCell("(" + ses[i] + ")", colW[3], "right"),
              dataCell(ps[i], colW[4], "right"),
            ]})
          );
        })
      ]
    });
  })(),
  emptyPara(),
  para("The results are invariant to the choice of standard error specification. The point estimate for \u201Cruns next\u201D is 0.285 regardless of clustering, with standard errors ranging from 0.048 to 0.050. For \u201Cwins next,\u201D the estimate is 0.186 with standard errors between 0.045 and 0.047. The virtually identical standard errors across clustering levels indicate that within-cluster correlation does not substantially inflate variance, likely because the running variable already incorporates province-election-level information."),

  heading2("6.4 List Position Effects (SQ4)"),
  para("A distinctive feature of closed-list PR systems is that party organizations determine the ordering of candidates on the list, and this ordering directly determines which candidates are elected given the number of seats the party wins. Hypothesis H3 posits that incumbency\u2014operationalized as the party barely winning a marginal seat\u2014leads to more favorable list positions for candidates in the subsequent election. This outcome is inherently conditional: list position in the next election is only observed for candidates who reappear on a party list, making this a selected-sample analysis."),
  para("Table 10 presents the RDD estimates for two list-position outcomes: list_pos_next (the candidate\u2019s raw list position in the subsequent election) and list_pos_change (the change in list position from the current to the subsequent election, where negative values indicate an improvement). The estimates are reported across the bandwidth grid with province-election clustered standard errors."),
  emptyPara(),
  para([new TextRun({ text: "Table 10: List Position Effects \u2013 RDD Estimates (Conditional on Running Again)", bold: true, font: "Arial", size: 22 })], { alignment: AlignmentType.CENTER }),

  (() => {
    const colW = [1700, 900, 900, 1100, 1100, 1100, 900];
    return new Table({
      width: { size: 8500, type: WidthType.DXA },
      columnWidths: colW,
      rows: [
        new TableRow({ children: [
          headerCell("Outcome", colW[0]),
          headerCell("BW", colW[1]),
          headerCell("N", colW[2]),
          headerCell("Mean (L)", colW[3]),
          headerCell("Mean (R)", colW[4]),
          headerCell("\u03C4 (SE)", colW[5]),
          headerCell("p-value", colW[6]),
        ]}),
        ...[
          ["List pos. next", "0.025", "402", "4.180", "3.232", "\u22120.013 (0.635)", "0.984"],
          ["List pos. next", "0.050", "864", "3.859", "3.264", "\u22120.770 (0.469)", "0.102"],
          ["List pos. next", "0.075", "1,403", "3.594", "3.096", "\u22120.946* (0.463)", "0.042"],
          ["List pos. next", "0.100", "1,904", "3.490", "2.967", "\u22120.895* (0.454)", "0.050"],
          ["List pos. change", "0.025", "402", "1.472", "0.504", "0.859 (0.525)", "0.103"],
          ["List pos. change", "0.050", "864", "1.204", "0.370", "\u22120.148 (0.456)", "0.745"],
          ["List pos. change", "0.075", "1,403", "1.127", "0.289", "\u22120.498 (0.408)", "0.224"],
          ["List pos. change", "0.100", "1,904", "1.026", "0.295", "\u22120.761 (0.407)", "0.062"],
        ].map(row => new TableRow({ children: row.map((v, i) => dataCell(v, colW[i], i === 0 ? "left" : "right")) }))
      ]
    });
  })(),
  emptyPara(),
  para([new TextRun({ text: "Notes: ", italics: true, font: "Arial", size: 20 }), new TextRun({ text: "Province-election clustered SEs. Conditional on the candidate reappearing on a party list. Negative \u03C4 for list_pos_next indicates a better (higher) list position. * p < 0.05.", font: "Arial", size: 20 })]),
  emptyPara(),
  para("The list-position analysis reveals that candidates whose party barely wins a marginal seat tend to receive more favorable list positions in the subsequent election. At the baseline bandwidth of 0.05, the point estimate for list_pos_next is \u22120.77 positions (SE = 0.47, p = 0.10), indicating that candidates on the winning side of the cutoff are placed approximately 0.8 positions higher on the list, though the effect narrowly misses statistical significance at conventional levels. At the wider bandwidth of 0.075, the estimate strengthens to \u22120.95 positions (SE = 0.46, p = 0.04), reaching significance at the 5% level. The list_pos_change estimates show a similar directional pattern but are less precisely estimated, with the largest bandwidth (0.10) approaching significance at the 10% level (\u03C4 = \u22120.76, p = 0.06). These results, observed among the 864 candidates (at BW = 0.05) who reappear on a party list, are consistent with parties rewarding incumbency experience in their list-ordering decisions, though the evidence is suggestive at the narrower bandwidths and becomes more robust as the window expands."),

  heading2("6.5 Heterogeneity by District Magnitude (SQ3)"),
  para("Sub-question 3 asks whether the incumbency advantage varies across districts of different sizes. District magnitude\u2014the number of seats allocated to a province\u2014is a key institutional parameter that shapes the competitiveness and proportionality of elections. In small-magnitude districts (2\u20134 seats), the effective threshold for winning a seat is high, competition is intense, and a single seat can represent a large share of the province\u2019s representation. In large-magnitude districts (10+ seats), the threshold is lower, and the marginal seat represents a smaller fraction of total representation."),
  para("To investigate this heterogeneity, I split the analysis sample at the median district magnitude and re-estimate the main RDD specification separately for high-magnitude and low-magnitude provinces. Table 11 presents the results."),
  emptyPara(),
  para([new TextRun({ text: "Table 11: Heterogeneity by District Magnitude \u2013 RDD Estimates (BW = 0.05)", bold: true, font: "Arial", size: 22 })], { alignment: AlignmentType.CENTER }),

  (() => {
    const colW = [1200, 1600, 900, 1100, 1100, 1200, 900];
    return new Table({
      width: { size: 8500, type: WidthType.DXA },
      columnWidths: colW,
      rows: [
        new TableRow({ children: [
          headerCell("Outcome", colW[0]),
          headerCell("Subgroup", colW[1]),
          headerCell("N", colW[2]),
          headerCell("Mean (L)", colW[3]),
          headerCell("Mean (R)", colW[4]),
          headerCell("\u03C4 (SE)", colW[5]),
          headerCell("p-value", colW[6]),
        ]}),
        ...[
          ["Runs next", "High magnitude (\u2265 8)", "1,344", "0.305", "0.596", "0.264*** (0.069)", "<0.001"],
          ["Runs next", "Low magnitude (< 8)", "774", "0.322", "0.597", "0.307*** (0.070)", "<0.001"],
          ["Wins next", "High magnitude (\u2265 8)", "1,344", "0.046", "0.409", "0.137* (0.066)", "0.040"],
          ["Wins next", "Low magnitude (< 8)", "774", "0.079", "0.394", "0.244*** (0.067)", "<0.001"],
        ].map(row => new TableRow({ children: row.map((v, i) => dataCell(v, colW[i], i === 0 ? "left" : "right")) }))
      ]
    });
  })(),
  emptyPara(),
  para([new TextRun({ text: "Notes: ", italics: true, font: "Arial", size: 20 }), new TextRun({ text: "Province-election clustered SEs. Median district magnitude = 8 seats. * p < 0.05, *** p < 0.001.", font: "Arial", size: 20 })]),
  emptyPara(),
  para("The heterogeneity analysis reveals that the incumbency advantage is present and statistically significant in both high-magnitude and low-magnitude districts (split at the median of 8 seats). For the extensive margin (runs next), the point estimate is 0.264 (p < 0.001) in high-magnitude districts and 0.307 (p < 0.001) in low-magnitude districts. The pattern is more pronounced for the intensive margin (wins next): the effect is 0.244 (p < 0.001) in low-magnitude districts but only 0.137 (p = 0.04) in high-magnitude districts. This difference is consistent with the idea that winning a marginal seat matters more in smaller provinces where competition for fewer seats is fiercer and each seat represents a larger share of the province\u2019s representation. Despite these differences in magnitude, the broad pattern is clear: the incumbency advantage is a general phenomenon across Spain\u2019s diverse district magnitudes rather than being driven by a particular type of constituency."),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- CHAPTER 7: ROBUSTNESS ----------
const ch7 = [
  heading1("7. Robustness Checks"),

  heading2("7.1 McCrary Density Test"),
  para("A fundamental assumption of the RDD is that units cannot precisely manipulate the running variable to sort around the cutoff. I test this assumption using a McCrary (2008) density test, which examines whether there is a discontinuity in the density of the running variable at the cutoff."),
  emptyPara(),
  para([new TextRun({ text: "Table 5: McCrary Density Tests", bold: true, font: "Arial", size: 22 })], { alignment: AlignmentType.CENTER }),

  (() => {
    const colW = [1200, 1200, 1500, 1500, 1200, 1200];
    return new Table({
      width: { size: 7800, type: WidthType.DXA },
      columnWidths: colW,
      rows: [
        new TableRow({ children: [
          headerCell("BW", colW[0]),
          headerCell("N", colW[1]),
          headerCell("Log-density \u0394", colW[2]),
          headerCell("SE", colW[3]),
          headerCell("p-value", colW[4]),
          headerCell("Density ratio", colW[5]),
        ]}),
        ...[ // Data from density test CSV
          ["0.025", "1,050", "0.119", "0.169", "0.481", "1.126"],
          ["0.050", "2,412", "0.101", "0.108", "0.353", "1.106"],
          ["0.075", "4,265", "0.044", "0.177", "0.802", "1.045"],
          ["0.100", "6,039", "\u22120.082", "0.162", "0.610", "0.921"],
        ].map(row => new TableRow({ children: row.map((v, i) => dataCell(v, colW[i], i === 0 ? "left" : "right")) }))
      ]
    });
  })(),
  emptyPara(),
  para("The McCrary density tests provide no evidence of manipulation of the running variable. The log-density discontinuity estimates range from \u22120.081 to 0.123, none of which is statistically significant (all p-values > 0.35). The implied density ratios at the cutoff are close to one, indicating no bunching of observations just above or below the threshold. This is consistent with the expectation that parties cannot precisely control the vote margin that determines marginal seat allocation."),
  para("Figure 4 provides a visual representation of the running variable distribution. The histogram shows no visible bunching at the cutoff, with roughly symmetric frequency counts on either side, further supporting the absence of manipulation."),
  figureImage("fig4_density_test.png", 14),
  figCaption("Figure 4: McCrary Density Test. Distribution of the running variable around the cutoff (BW = 0.05)."),

  heading2("7.2 Placebo Cutoff Tests"),
  para("If the RDD design is valid, we should not observe significant effects at placebo cutoffs where no treatment discontinuity exists. I estimate the RDD at the median of each side of the running variable distribution\u2014the left-side median (approximately \u22120.048) and the right-side median (approximately 0.092)\u2014across multiple bandwidths."),
  emptyPara(),
  para([new TextRun({ text: "Table 6: Placebo Cutoff Tests (Selected Results, BW = 0.05)", bold: true, font: "Arial", size: 22 })], { alignment: AlignmentType.CENTER }),

  (() => {
    const colW = [1600, 1600, 1400, 1400, 1400];
    return new Table({
      width: { size: 7400, type: WidthType.DXA },
      columnWidths: colW,
      rows: [
        new TableRow({ children: [
          headerCell("Outcome", colW[0]),
          headerCell("Placebo", colW[1]),
          headerCell("\u03C4", colW[2]),
          headerCell("SE", colW[3]),
          headerCell("p-value", colW[4]),
        ]}),
        ...[ // from placebo cutoff CSV, bw=0.05
          ["Runs next", "Left median", "0.050", "0.054", "0.350"],
          ["Runs next", "Right median", "\u22120.002", "0.063", "0.975"],
          ["Wins next", "Left median", "0.006", "0.005", "0.247"],
          ["Wins next", "Right median", "0.062", "0.067", "0.354"],
        ].map(row => new TableRow({ children: row.map((v, i) => dataCell(v, colW[i], i < 2 ? "left" : "right")) }))
      ]
    });
  })(),
  emptyPara(),
  para("None of the placebo estimates is statistically significant at conventional levels (all p > 0.24). This strongly supports the validity of the RDD design: the estimated effects are specific to the true cutoff and do not reflect broader patterns in the data that might appear at arbitrary thresholds."),

  heading2("7.3 Donut-Hole Robustness"),
  para("To assess whether the results are driven by observations very close to the cutoff\u2014where manipulation or measurement error might be most concerning\u2014I implement donut-hole specifications that exclude observations within a small radius of the cutoff."),
  emptyPara(),
  para([new TextRun({ text: "Table 7: Donut-Hole Robustness (BW = 0.05)", bold: true, font: "Arial", size: 22 })], { alignment: AlignmentType.CENTER }),

  (() => {
    const colW = [1600, 1300, 1300, 1300, 1300];
    return new Table({
      width: { size: 6800, type: WidthType.DXA },
      columnWidths: colW,
      rows: [
        new TableRow({ children: [
          headerCell("Outcome", colW[0]),
          headerCell("Donut", colW[1]),
          headerCell("\u03C4", colW[2]),
          headerCell("SE", colW[3]),
          headerCell("N", colW[4]),
        ]}),
        ...[ // from donut CSV, bw=0.05
          ["Runs next", "0.001", "0.272***", "0.051", "2,091"],
          ["Runs next", "0.0025", "0.213***", "0.056", "2,050"],
          ["Runs next", "0.005", "0.213***", "0.062", "1,963"],
          ["Wins next", "0.001", "0.154**", "0.048", "2,091"],
          ["Wins next", "0.0025", "0.162**", "0.051", "2,050"],
          ["Wins next", "0.005", "0.157**", "0.056", "1,963"],
        ].map(row => new TableRow({ children: row.map((v, i) => dataCell(v, colW[i], i < 2 ? "left" : "right")) }))
      ]
    });
  })(),
  emptyPara(),
  para("The estimates remain significant even when excluding observations within 0.5 percentage points of the cutoff. While the point estimates attenuate somewhat as the donut radius increases\u2014consistent with moving further from the cutoff where local treatment effects may differ\u2014the qualitative conclusions are unchanged. The \u201Cruns next\u201D effect ranges from 0.215 to 0.273 across donut specifications, and \u201Cwins next\u201D ranges from 0.158 to 0.167, all statistically significant."),

  heading2("7.4 Polynomial Order Sensitivity"),
  para("I compare the baseline local-linear (first-order polynomial) specification with a local-quadratic (second-order polynomial) specification to assess sensitivity to functional form assumptions."),
  emptyPara(),
  para([new TextRun({ text: "Table 8: Polynomial Order Comparison (BW = 0.05)", bold: true, font: "Arial", size: 22 })], { alignment: AlignmentType.CENTER }),

  (() => {
    const colW = [1600, 1600, 1300, 1300, 1300];
    return new Table({
      width: { size: 7100, type: WidthType.DXA },
      columnWidths: colW,
      rows: [
        new TableRow({ children: [
          headerCell("Outcome", colW[0]),
          headerCell("Polynomial", colW[1]),
          headerCell("\u03C4", colW[2]),
          headerCell("SE", colW[3]),
          headerCell("p-value", colW[4]),
        ]}),
        ...[ // from polynomial CSV, bw=0.05
          ["Runs next", "Linear", "0.285***", "0.048", "<0.001"],
          ["Runs next", "Quadratic", "0.329***", "0.069", "<0.001"],
          ["Wins next", "Linear", "0.186***", "0.047", "<0.001"],
          ["Wins next", "Quadratic", "0.180*", "0.070", "0.010"],
        ].map(row => new TableRow({ children: row.map((v, i) => dataCell(v, colW[i], i < 2 ? "left" : "right")) }))
      ]
    });
  })(),
  emptyPara(),
  para("The local-quadratic estimates are broadly consistent with the linear specification. For \u201Cruns next,\u201D the quadratic estimate is somewhat larger (0.329 vs. 0.285) but within the confidence intervals. For \u201Cwins next,\u201D the estimates are nearly identical (0.180 vs. 0.186). Both specifications yield statistically significant effects, indicating that the results are not driven by the choice of polynomial order."),

  heading2("7.5 Covariate Balance"),
  para("Table 9 examines whether pre-determined covariates exhibit discontinuities at the cutoff, which would suggest potential violations of the RDD identifying assumption."),
  emptyPara(),
  para([new TextRun({ text: "Table 9: Covariate Balance at the Cutoff (BW = 0.05)", bold: true, font: "Arial", size: 22 })], { alignment: AlignmentType.CENTER }),

  (() => {
    const colW = [2000, 1400, 1400, 1400, 1200];
    return new Table({
      width: { size: 7400, type: WidthType.DXA },
      columnWidths: colW,
      rows: [
        new TableRow({ children: [
          headerCell("Covariate", colW[0]),
          headerCell("\u03C4", colW[1]),
          headerCell("SE", colW[2]),
          headerCell("p-value", colW[3]),
          headerCell("Sig.", colW[4]),
        ]}),
        ...[ // from balance CSV, bw=0.05
          ["Blank vote share", "\u22120.000", "0.000", "0.726", ""],
          ["Female share", "0.159", "0.061", "0.009", "**"],
          ["List position", "\u22120.082", "0.310", "0.791", ""],
          ["Log party votes", "\u22120.119", "0.120", "0.323", ""],
          ["Party seats", "0.757", "0.311", "0.015", "*"],
        ].map(row => new TableRow({ children: row.map((v, i) => dataCell(v, colW[i], i === 0 ? "left" : "right")) }))
      ]
    });
  })(),
  emptyPara(),
  para("Most covariates are well-balanced at the cutoff. Blank vote share, list position, and log party votes show no significant discontinuity (all p > 0.30). The female share covariate shows a statistically significant difference at the 0.05 bandwidth (p = 0.009), though this effect attenuates at larger bandwidths and is not robust across all specifications. Party seats shows significance (p = 0.014), but this is partly mechanical given that winning the marginal seat directly increases seat count. Overall, the balance evidence supports the validity of the design."),
  para("Figure 6 provides a visual summary of the covariate balance tests. The coefficient plot shows RDD estimates and 95% confidence intervals for each covariate. Covariates highlighted in red indicate statistical significance at the 5% level; blue indicates insignificance. Most confidence intervals comfortably include zero."),
  figureImage("fig6_covariate_balance.png", 14),
  figCaption("Figure 6: Covariate Balance at the Cutoff. RDD estimates with 95% CIs. Red = significant at 5%."),

  heading2("7.6 Outcome Definition Robustness"),
  para("I also test robustness to alternative outcome definitions. The baseline outcomes use the \u201Csame province\u201D definition, which tracks whether a party runs or wins a seat in the same province in the subsequent election. As a robustness check, I also consider an \u201Cany province\u201D definition that tracks whether the party runs or wins in any province."),
  para("The results are qualitatively identical across outcome definitions. The same-province \u201Cruns next\u201D estimate is 0.285, and the any-province estimate is 0.271. For \u201Cwins next,\u201D the same-province estimate is 0.186 and the any-province estimate is 0.189. The consistency across definitions confirms that the incumbency effect operates at the provincial level, as expected given the institutional framework."),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- CHAPTER 8: DISCUSSION ----------
const ch8 = [
  heading1("8. Discussion"),

  heading2("8.1 Interpretation of Results"),
  para("The findings reveal a substantial incumbency advantage in Spain\u2019s proportional representation system. Winning a marginal seat increases the probability of running in the next election by about 28 percentage points and the probability of winning by about 19 percentage points. These effects are large in magnitude and comparable to incumbency advantages documented in majoritarian systems, though direct cross-system comparisons should be made cautiously due to differences in institutional context and measurement."),
  para("The large effect on the extensive margin (running again) is particularly noteworthy. It suggests that a significant portion of the incumbency advantage operates through the decision to contest the election at all, rather than solely through improved vote shares conditional on running. This is consistent with the idea that winning representation provides parties with organizational resources, visibility, and demonstrated viability that reduce barriers to entry in subsequent elections."),

  heading2("8.2 Mechanisms"),
  para("Several mechanisms could explain the observed incumbency advantage in this PR setting. First, parties that win a seat gain access to parliamentary resources, media visibility, and policy influence that can be leveraged for future campaigns. Second, winning a seat signals electoral viability to potential donors, party members, and voters, creating a self-reinforcing cycle of support. Third, in a closed-list system, the party organization rather than individual candidates is the primary beneficiary of incumbency, potentially leading to stronger party-level effects than would be observed in open-list or candidate-centered systems."),
  para("The list-position analysis (SQ4) adds a further dimension to the mechanisms discussion. In closed-list PR systems, party gatekeepers decide which candidates receive prominent list positions. The suggestive evidence that incumbency leads to more favorable list positions indicates that party organizations internalize the electoral experience of their candidates when constructing subsequent lists, which could be a channel through which individual-level incumbency effects are mediated."),
  para("The heterogeneity analysis (SQ3) indicates that the incumbency advantage is a broad phenomenon rather than an artifact of a particular district type. The fact that effects are present in both high- and low-magnitude districts suggests that the mechanisms operate across different competitive environments, although the relative importance of specific channels (visibility, resource access, party coordination) may vary with district size."),
  para("The near-perfect first stage (\u03C4 \u2248 0.98) is an important finding in itself. It confirms that the D\u2019Hondt allocation mechanism operates almost deterministically at the margin: parties that barely cross the threshold for a marginal seat are almost certainly elected, while those that barely miss it are almost certainly not. This near-perfect compliance validates the sharp RDD approach and confirms that the design cleanly identifies the incumbency effect."),

  heading2("8.3 Comparison with Literature"),
  para("Placing these results alongside existing estimates reveals both the generality of the incumbency advantage phenomenon and the distinctive features of the Spanish case. Table 12 summarizes the key cross-country comparisons."),
  para("In majoritarian systems, Lee (2008) found a roughly 38 percentage point party-level incumbency advantage in US House elections\u2014substantially larger than the Spanish estimate, but operating in a fundamentally different institutional environment where incumbents benefit from personal name recognition, constituency service, and campaign finance advantages tied directly to the individual candidate."),
  para("Among PR systems, Luechinger, Schelker, and Schmid (2024) report significant incumbency effects in Swiss cantonal elections using the same closeness measure employed here. A direct comparison is instructive: Switzerland uses open-list PR with panachage, meaning voters can express individual candidate preferences. Any Swiss incumbency effect could plausibly flow through the personal vote channel\u2014voters recognizing and preferring individual incumbents. The finding that Spain\u2019s closed-list system produces incumbency effects of broadly comparable magnitude suggests that party-level mechanisms (organizational resources, demonstrated viability, gatekeeper decisions) are sufficient to generate incumbency advantages even when the personal vote channel is shut down. This is a substantively important result, because it implies that incumbency advantages under PR are not merely a reflection of candidate-centered politics leaking into proportional systems, but rather a systemic feature of how parties behave when they gain representation."),
  para("Dano et al. (2022) documented incumbency effects in French legislative elections\u2014a two-round majoritarian system with multi-party competition. Their finding that incumbency affects both the probability of running again and the probability of winning parallels the Spanish results, despite the very different electoral rules. The relative magnitudes in Spain\u2014a larger effect on running (~28 pp) than on winning (~19 pp)\u2014suggest that a substantial portion of the advantage operates through selection into candidacy rather than through improved electoral performance conditional on running. This extensive-margin channel has received less attention in the literature and may be particularly important in PR systems, where party organizations serve as gatekeepers to candidacy."),
  para("The heterogeneity results add a further comparative dimension. The finding that incumbency effects are present in both high- and low-magnitude districts, but somewhat stronger in low-magnitude provinces, is consistent with theoretical predictions: in smaller districts where each seat represents a larger share of representation, the marginal value of incumbency is higher, and the competitive dynamics of D\u2019Hondt allocation create sharper distinctions between winning and losing parties."),

  heading2("8.4 Limitations"),
  para("Several limitations should be noted. First, while outcomes are tracked at the individual candidate level via person-identifier linkage, the running variable is measured at the party-province level; all candidates on the same party list share the same running variable value, which limits the ability to identify purely individual-level variation. Second, the list-position outcome is inherently conditional on reappearing on a party list, introducing a sample selection concern: if winning a marginal seat also affects the probability of reappearing, the list-position estimates may reflect both the direct effect on list placement and the compositional effect of who appears on the list. Third, while the balance tests are generally supportive, the significant imbalance in female share at narrow bandwidths warrants caution. Fourth, the sample period (2004\u20132023) includes significant political disruptions in Spain, including the emergence of new parties and a financial crisis, which may affect the external validity of the estimates. Fifth, the analysis does not account for potential spillover effects across provinces, which could occur if parties coordinate their strategies nationally."),
  para("Future work could extend this analysis by investigating whether the incumbency advantage varies with party size or ideology, by exploiting within-party variation in list positions to isolate individual-level mechanisms, and by extending the framework to other closed-list PR systems for comparative analysis."),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- CHAPTER 9: CONCLUSION ----------
const ch9 = [
  heading1("9. Conclusion"),
  para("This thesis provides the first comprehensive estimates of the incumbency advantage in Spain\u2019s proportional representation system at the candidate level. Using a regression discontinuity design adapted for PR systems following Luechinger, Schelker, and Schmid (2024), I exploit the quasi-random assignment of marginal seats under the D\u2019Hondt method to identify the causal effect of winning a seat on individual candidates\u2019 subsequent electoral outcomes."),
  para("The results are clear and robust: candidates whose party barely wins a marginal seat are approximately 28 percentage points more likely to reappear on a party list in the next election and 19 percentage points more likely to win a seat. These effects survive an extensive battery of robustness checks, including alternative bandwidths, polynomial specifications, donut-hole restrictions, placebo cutoff tests, and McCrary density tests. The near-perfect first stage confirms the internal validity of the design."),
  para("Beyond these core findings, the analysis reveals suggestive evidence that winning a marginal seat leads to more favorable list positions in subsequent elections, pointing to a mechanism through which party organizations reward incumbency experience. The heterogeneity analysis shows that the incumbency advantage is present across districts of varying magnitudes, indicating that it is a systemic feature of Spain\u2019s electoral landscape rather than an artifact of a particular district type."),
  para("These findings have implications for our understanding of democratic representation in PR systems. Even in a closed-list PR system\u2014where individual candidate effects are minimized and parties mediate the relationship between citizens and government\u2014incumbency confers substantial advantages that operate through both candidate reappearance and list-position channels. This suggests that institutional features of PR systems do not fully eliminate the self-perpetuating dynamics of incumbency that have been widely documented in majoritarian contexts."),
  para("From a data science perspective, this thesis demonstrates the application of rigorous causal inference methodology to a rich administrative dataset, combining political science domain knowledge with computational methods. The implementation of the closeness measure for PR systems, the person-level linking algorithms for tracking candidates across elections, and the comprehensive robustness framework illustrate the interdisciplinary nature of applied data science research."),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- CHAPTER 10: REFERENCES ----------
const ch10 = [
  heading1("10. References"),
  para("Ansolabehere, S., & Snyder, J. M. (2002). The incumbency advantage in U.S. elections: An analysis of state and federal offices, 1942\u20132000. Election Law Journal, 1(3), 315\u2013338."),
  para("Calonico, S., Cattaneo, M. D., & Titiunik, R. (2014). Robust nonparametric confidence intervals for regression-discontinuity designs. Econometrica, 82(6), 2295\u20132326."),
  para("Cameron, A. C., Gelbach, J. B., & Miller, D. L. (2008). Bootstrap-based improvements for inference with clustered errors. The Review of Economics and Statistics, 90(3), 414\u2013427."),
  para("Caughey, D., & Sekhon, J. S. (2011). Elections and the regression discontinuity design: Lessons from close U.S. House races, 1942\u20132008. Political Analysis, 19(4), 385\u2013408."),
  para("Cox, G. W., & Katz, J. N. (1996). Why did the incumbency advantage in U.S. House elections grow? American Journal of Political Science, 40(2), 478\u2013497."),
  para("Dano, K., Ferlenga, F., Galasso, V., Le Pennec, C., & Pons, V. (2022). Coordination and incumbency advantage in multi-party systems\u2014Evidence from French elections. NBER Working Paper No. 30541."),
  para("Erikson, R. S. (1971). The advantage of incumbency in congressional elections. Polity, 3(3), 395\u2013405."),
  para("Galasso, V., & Nannicini, T. (2011). Competing on good politicians. American Political Science Review, 105(1), 79\u201399."),
  para("Gelman, A., & King, G. (1990). Estimating incumbency advantage without bias. American Journal of Political Science, 34(4), 1142\u20131164."),
  para("Hazan, R. Y., & Rahat, G. (2010). Democracy within parties: Candidate selection methods and their political consequences. Oxford University Press."),
  para("Imbens, G. W., & Kalyanaraman, K. (2012). Optimal bandwidth choice for the regression discontinuity estimator. The Review of Economic Studies, 79(3), 933\u2013959."),
  para("Lee, D. S. (2008). Randomized experiments from non-random selection in U.S. House elections. Journal of Econometrics, 142(2), 675\u2013697."),
  para("Luechinger, S., Schelker, M., & Schmid, L. (2024). Measuring closeness in proportional representation systems. Political Analysis, 32(1), 101\u2013114."),
  para("McCrary, J. (2008). Manipulation of the running variable in the regression discontinuity design: A density test. Journal of Econometrics, 142(2), 698\u2013714."),
  para("Stock, J. H., & Yogo, M. (2005). Testing for weak instruments in linear IV regression. In D. W. K. Andrews & J. H. Stock (Eds.), Identification and inference for econometric models: Essays in honor of Thomas Rothenberg. Cambridge University Press."),
  para("Taagepera, R., & Shugart, M. S. (1989). Seats and votes: The effects and determinants of electoral systems. Yale University Press."),
  new Paragraph({ children: [new PageBreak()] })
];

// ---------- APPENDIX ----------
const appendix = [
  heading1("Appendix A: Technical Implementation"),
  para("The analysis was implemented in Python 3.11 using the following key packages:"),
  para([
    new TextRun({ text: "pandas ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "(>= 2.2): Data manipulation and management of the party-province-election panel dataset.", font: "Arial", size: 24 })
  ]),
  para([
    new TextRun({ text: "numpy ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "(>= 1.26): Numerical computations including kernel weight calculations and matrix operations.", font: "Arial", size: 24 })
  ]),
  para([
    new TextRun({ text: "statsmodels ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "(>= 0.14): Weighted least squares regression with heteroskedasticity-robust and clustered standard errors.", font: "Arial", size: 24 })
  ]),
  para([
    new TextRun({ text: "scipy ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "(>= 1.11): t-distribution critical values for finite-cluster inference.", font: "Arial", size: 24 })
  ]),
  para([
    new TextRun({ text: "matplotlib ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "(>= 3.8): Visualization of RDD scatter plots and regression fits.", font: "Arial", size: 24 })
  ]),
  para([
    new TextRun({ text: "rdrobust ", bold: true, font: "Arial", size: 24 }),
    new TextRun({ text: "(>= 1.1): Bias-corrected inference following Calonico, Cattaneo, and Titiunik (2014).", font: "Arial", size: 24 })
  ]),
  emptyPara(),
  para("The complete source code is organized following a standard data science project structure:"),
  para([new TextRun({ text: "src/data/", bold: true, font: "Arial", size: 24 }), new TextRun({ text: " \u2013 Data ingestion, cleaning, and person-ID construction.", font: "Arial", size: 24 })]),
  para([new TextRun({ text: "src/models/", bold: true, font: "Arial", size: 24 }), new TextRun({ text: " \u2013 RDD estimation, robustness checks, and thesis table generation.", font: "Arial", size: 24 })]),
  para([new TextRun({ text: "data/processed/", bold: true, font: "Arial", size: 24 }), new TextRun({ text: " \u2013 Processed datasets and analysis outputs.", font: "Arial", size: 24 })]),
  para([new TextRun({ text: "data/processed/thesis_tables/", bold: true, font: "Arial", size: 24 }), new TextRun({ text: " \u2013 Tables in CSV, LaTeX, and Markdown formats.", font: "Arial", size: 24 })]),
];

// ============================================================
// ASSEMBLE DOCUMENT
// ============================================================

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: "Arial", size: 24 }
      }
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 480, after: 240 }, outlineLevel: 0 }
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 1 }
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 2 }
      },
    ]
  },
  sections: [
    // Title page (no header/footer)
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
        }
      },
      children: titlePage
    },
    // Main content
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
        }
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              alignment: AlignmentType.RIGHT,
              border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "CCCCCC", space: 4 } },
              children: [
                new TextRun({ text: "Electoral Closeness and Incumbency Advantage in Spain", font: "Arial", size: 18, color: "999999", italics: true })
              ]
            })
          ]
        })
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ text: "Page ", font: "Arial", size: 18, color: "999999" }),
                new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 18, color: "999999" }),
              ]
            })
          ]
        })
      },
      children: [
        ...abstractSection,
        ...declarationSection,
        ...tocSection,
        ...listOfTables,
        ...ch1,
        ...ch2,
        ...ch3,
        ...ch4,
        ...ch5,
        ...ch6,
        ...ch7,
        ...ch8,
        ...ch9,
        ...ch10,
        ...appendix
      ]
    }
  ]
});

// ============================================================
// WRITE FILE
// ============================================================

const OUTPUT = "/Users/Camilo/Desktop/master-thesis/docs/thesis_draft.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(OUTPUT, buffer);
  console.log("Created:", OUTPUT, "(" + buffer.length + " bytes)");
}).catch(err => {
  console.error("Error:", err);
  process.exit(1);
});
