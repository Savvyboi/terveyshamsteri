// Topic tags for agenda items, from keywords in the item's title (Finnish and Swedish stems).
// Titles are short and chosen by the preparer, so they say what an item is about more
// reliably than the body text, which mentions everything in passing. An item can have
// several topics or none; procedural items (quorum, minutes checkers, notices) get none.
import type { Bilingual } from './data';

export interface Topic { id: string; label: Bilingual; re: RegExp }

const t = (id: string, fi: string, sv: string, en: string, stems: string): Topic =>
  ({ id, label: { fi, sv, en }, re: new RegExp(stems, 'i') });

export const TOPICS: Topic[] = [
  t('talous', 'Talous ja budjetti', 'Ekonomi och budget', 'Finances and budget',
    'talou|tilinpäätö|toimintakertomu|osavuosi|alijäämä|ylijäämä|tasapainott|säästö|sopeutt|tuottavuu|budjet|määrärah|lainanot|rahoitu|talouden|taloudelli|tilintarkast|investointiohjelm|' +
    'budget|bokslut|ekonomi|verksamhetsberättel|delårs|underskott|överskott|balanser|sparåtgärd|anpassning|produktivitet|anslag|finansiering|revision'),
  t('henkilosto', 'Henkilöstö', 'Personal', 'Staff',
    'henkilöst|viran |virkojen|virka|virkanimik|toimen perust|täyttölupa|palkka|palkkau|palkkio|työehto|muutosneuvottel|yhteistoimintaneuvottel|lomautu|rekrytoin|työhyvinvoin|työsuojel|' +
    'personal|tjänst|befattning|lön|arvode|permitter|rekryt|samarbetsförhandl|arbetarskydd'),
  t('hankinnat', 'Hankinnat ja sopimukset', 'Upphandlingar och avtal', 'Procurement and contracts',
    'hankin|kilpailut|sopimu|puitejärjest|ostopalvel|palvelusetel|monituottaja|yksityis|ulkoista|' +
    'upphandl|avtal|köptjänst|servicesedel|privat|utlokaliser'),
  t('tilat', 'Tilat ja investoinnit', 'Lokaler och investeringar', 'Premises and investments',
    'kiinteist|investoin|rakennu|peruskorja|uudisrakent|tilaratkais|tilojen|tilat\\b|toimitil|vuokra|hankesuunnitel|tarveselvity|sairaalahanke|' +
    'fastighet|investering|lokal|ombyggn|nybygg|hyresavtal|byggnad|projektplan'),
  t('palveluverkko', 'Palveluverkko', 'Servicenätverk', 'Service network',
    'palveluverk|terveysasem|sote-keskus|sote-pist|sote-asem|toimipist|palvelupist|lakkaut|hyvinvointikeskus|aukiolo|palvelujen järjestämis|järjestämissuunnit|palvelustrategi|' +
    'servicenät|hälsostation|vårdcentral|social- och hälsocentral|indrag|stängning|servicepunkt|välfärdscentral|öppettid|servicestrategi'),
  t('terveydenhuolto', 'Terveydenhuolto', 'Hälso- och sjukvård', 'Health care',
    'terveydenhuol|sairaala|erikoissairaanh|päivystys|perusterv|lääkär|hoitaja|vastaanot|suun terv|hammas|kuntoutu|synnyty|leikkau|hoitotak|jono|potila|' +
    'sjukvård|sjukhus|jour|primärvård|läkare|skötare|mottagning|tandvård|rehabilit|förlossning|vårdgaranti|patient'),
  t('sosiaalipalvelut', 'Sosiaalipalvelut', 'Socialservice', 'Social services',
    'sosiaalityö|sosiaalipalvel|kuljetuspalvel|liikkumisen tu|matkabudjet|färdtjänst|sosiaalihuol|sosiaaliohjau|toimeentulo|aikuissosiaal|asumispalvel|asunnottom|kotoutu|maahanmuut|työllisyy|kuntouttava|' +
    'socialarbete|socialservice|socialvård|socialhandledning|utkomststöd|boendeservice|bostadslös|integration|invandr|sysselsättning'),
  t('ikaantyneet', 'Ikääntyneet', 'Äldre', 'Older people',
    'ikäänty|vanhus|vanhust|kotihoi|ympärivuorokau|palveluasu|hoivako|omaishoi|muistisairau|' +
    'äldre|hemvård|dygnet runt|serviceboende|närståendevård|minnessjuk'),
  t('lapset', 'Lapset, nuoret ja perheet', 'Barn, unga och familjer', 'Children, young people and families',
    'lapsi|lasten|lapsiper|nuor|perhe|lastensuojel|neuvola|koulutervey|opiskeluterv|kasvatus|koulu|' +
    'barn|unga\\b|ungdom|familj|barnskydd|rådgivning|skolhälso|studerandehälso|uppfostr|skola'),
  t('mielenterveys', 'Mielenterveys ja päihteet', 'Mental hälsa och missbruk', 'Mental health and substance use',
    'mielenterv|päihde|päihtei|riippuvuu|psykiatr|psykososiaal|' +
    'mental|missbruk|psykiatri|beroende|psykosocial'),
  t('vammaispalvelut', 'Vammaispalvelut', 'Funktionshinderservice', 'Disability services',
    'vammai|kehitysvamm|' +
    'funktionshind|handikapp|funktionsnedsätt|utvecklingsstörn'),
  t('pelastus', 'Pelastus ja ensihoito', 'Räddning och prehospital vård', 'Rescue and emergency care',
    'pelastu|palokun|paloasem|ensihoi|varautu|valmiussuunnit|turvallisuu|' +
    'räddning|brandkår|brandstation|prehospital|ambulans|beredskap|säkerhet'),
  t('asiakasmaksut', 'Asiakasmaksut', 'Klientavgifter', 'Client fees',
    'asiakasmaks|palvelumaks|maksukat|hinnast|taksa|maksut|' +
    'klientavgift|avgift|taxa|prislista'),
  t('hyvinvointi', 'Hyvinvoinnin edistäminen', 'Främjande av välfärd', 'Health and wellbeing promotion',
    'edistä|hyvinvointisuunnitel|hyvinvointikertom|hyvinvointiraport|järjestö|osallisuu|kolmas sektori|' +
    'främj|förebygg|välfärdsplan|välfärdsberättelse|organisation|delaktighet'),
  t('digitalisaatio', 'Digitalisaatio', 'Digitalisering', 'Digitalisation',
    'digi|tietojärjest|asiakastietojärj|potilastietojärj|sähköi|tekoäly|tietoturva|tiedonhallin|' +
    'informationssystem|elektronisk|artificiell|datasäkerhet|informationshantering'),
  t('aloitteet', 'Aloitteet', 'Motioner och initiativ', 'Motions and initiatives',
    'aloite|aloitteeseen|aloitteen|aloitteet|' +
    'motion|initiativ'),
  t('oikaisut', 'Oikaisuvaatimukset ja valitukset', 'Omprövningar och besvär', 'Appeals and complaints',
    'oikaisuvaatim|valitu|hallinto-oikeu|kantelu|muistutu|' +
    'omprövning|besvär|förvaltningsdomstol|klagomål|anmärkning'),
  t('hallinto', 'Hallinto ja luottamushenkilöt', 'Förvaltning och förtroendevalda', 'Governance and elected officials',
    'hallintosään|yhtiö|konserni|osake|omavalvon|valvonta|riskienhallin|sisäinen tarkast|sisäisen tarkast|bolag|koncern|egenkontroll|tillsyn|riskhantering|internrevision|luottamushenkil|luottamustoim|eronpyyn|vaali|valinta|valitseminen|edustaj|toimintasään|strategi|johtosään|nimeämi|nimittämi|neuvosto|sidonnaisuu|tarkastuslautakun|arviointikertom|' +
    'förvaltningsstadga|förtroendevald|förtroendeuppdrag|befrielse|val av|utseende|utse|representant|instruktion|strategi|bindningar|revisionsnämnd|utvärderingsberättelse|råd\\b|rådet'),
];

// Standing items of every meeting. They say nothing about what was decided.
const PROCEDURAL = new RegExp([
  'pöytäkirjan ?tarkast', 'pöytäkirjantarkast', 'laillisuu', 'päätösvaltai', 'työjärjesty', 'kokouksen (?:avaus|avaaminen|päättäminen|järjestäytyminen)',
  '^muut (?:mahdolliset )?asiat', '^tiedoksi', 'tiedoksi (?:merkittävät|annettavat|saatettavat)', 'tiedoksisaatettavat', 'ilmoitusasiat', 'ajankohtai',
  'esityslistan hyväksy', 'käsittelyjärjest', 'seuraava(?:n)? kokou', 'kokousaikatau', 'kokoukset', 'lainvoimai', 'täytäntöönpano', 'sammanträdestid', 'kysymyksiä, aloitteita ja ilmoituksia',
  'protokolljuster', 'justering av protokoll', 'protokollsjuster', 'laglighet', 'beslutsförhet', 'föredragningslist', 'arbetsordning', 'övriga ärenden',
  'meddelanden', 'aktualitet', 'lägesrapport', 'lägesöversikt', '^infot?$', 'för kännedom', 'delgivning', 'ottomenettely', 'otto-oikeu', 'viranhaltijoiden päätö', 'ordförandens',
].join('|'), 'i');

export const topicById = (id: string) => TOPICS.find((x) => x.id === id);

const cache = new Map<string, string[]>();
/** Topic ids of an item with this title. */
export function topicsOf(title: string): string[] {
  let out = cache.get(title);
  if (!out) {
    out = PROCEDURAL.test(title) ? [] : TOPICS.filter((x) => x.re.test(title)).map((x) => x.id);
    cache.set(title, out);
  }
  return out;
}
