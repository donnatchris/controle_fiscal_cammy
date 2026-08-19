import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from shared.constantes import SEPARATEUR_SIGNATURE, SEPARATEUR_TICKET
from shared.parse_money import parse_money


@dataclass
class EjLigneTicket:
    D_QUANTITE_ARTICLE: int | None = None
    D_LIBELLE_ARTICLE: str | None = None
    D_TAUX_TVA_ARTICLE: str | None = None
    D_MONTANT_ARTICLE: Decimal | None = None
    D_CORRECTION: Decimal | None = None
    D_AUTRE_INFO: str | None = None


@dataclass
class EjEnteteTicket:
    nomFichier: str
    boutique: str
    E_NUM_INTERNE: str
    E_DATE_TICKET: date
    E_HEURE_TICKET: str
    type: str
    signature: str | None = None
    evenement: str | None = None

    E_NUM_TICKET: str | None = None

    E_HT1: Decimal | None = None
    E_HT2: Decimal | None = None
    E_HT3: Decimal | None = None
    E_HT4: Decimal | None = None

    E_TVA1: Decimal | None = None
    E_TVA2: Decimal | None = None
    E_TVA3: Decimal | None = None
    E_TVA4: Decimal | None = None

    E_HT_NON_TAXABLE: Decimal | None = None

    E_TTC: Decimal | None = None

    E_MDP_CB: Decimal | None = None
    E_MDP_ESPECES: Decimal | None = None
    E_MDP_CHEQUES: Decimal | None = None


@dataclass
class EjTicket:
    entete: EjEnteteTicket
    lignes_articles: list[EjLigneTicket] = field(default_factory=list)
    _PATTERN_ENTETE = r"(\S+)\s+(\d{2}-\d{2}-\d{4})\s+(\d{2}:\d{2})"
    _STARTING_LINE: str = SEPARATEUR_TICKET
    _ENDING_LINE: str = SEPARATEUR_SIGNATURE
    _PATTERN_LIGNE_ARTICLE = re.compile(
        r"^\s*(?P<quantite>\d+)\s*"
        r"(?P<libelle>.*?)\s*"
        r"(?P<taux>T\d+)\s+"
        r"(?P<montant>[€$]?\s*-?[\d\s.,]+)\s*$"
    )

    @classmethod
    def _parse_header(cls, header: list[str]) -> tuple[str, date, str, str]:
        """Parse le header du ticket et retourne le type, la date, l'heure et le numéro interne."""
        if not header:
            raise ValueError(
                "Le ticket ne contient pas d'entête après la ligne de démarcation"
            )
        header_line = header.pop(0).strip()
        match = re.fullmatch(EjTicket._PATTERN_ENTETE, header_line)
        if not match:
            raise ValueError(f"Entête de ticket invalide : {header_line!r}")

        type, date_str, heure_str = match.groups()

        E_DATE_TICKET = datetime.strptime(
            date_str,
            "%d-%m-%Y",
        ).date()

        E_HEURE_TICKET = heure_str

        try:
            datetime.strptime(heure_str, "%H:%M")
        except ValueError as exc:
            raise ValueError(f"Heure de ticket invalide : {heure_str!r}") from exc

        if not header:
            raise ValueError("Le ticket ne contient pas de numéro interne")

        E_NUM_INTERNE = header.pop(0).strip()

        if not E_NUM_INTERNE:
            raise ValueError("Le ticket ne contient pas de numéro interne")

        return type, E_DATE_TICKET, E_HEURE_TICKET, E_NUM_INTERNE

    @classmethod
    def _parse_signature(cls, signature_lines: list[str]) -> str:
        """Parse la signature du ticket et retourne la signature sous forme de chaîne de caractères."""
        signature = ""
        if not signature_lines:
            raise ValueError("Le ticket ne contient pas de signature")
        if signature_lines[0].strip().startswith(EjTicket._ENDING_LINE):
            signature_lines.pop(0)
        if not signature_lines:
            raise ValueError(
                "Le ticket ne contient pas de signature après la ligne de démarcation"
            )
        for line in signature_lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith(EjTicket._STARTING_LINE) or line.startswith(
                EjTicket._ENDING_LINE
            ):
                raise ValueError(
                    "Le ticket contient une ligne de démarcation inattendue dans la signature"
                )
            signature += line + "\n"
        return signature.strip()

    @staticmethod
    def _pop_next_line(lines: list[str], *, error_message: str) -> str:
        """Retire la ligne suivante ou signale un bloc de ticket tronqué."""
        if not lines:
            raise ValueError(error_message)
        return lines.pop(0).strip()

    @staticmethod
    def _montant_signe(value: Decimal | None, type_ticket: str) -> Decimal | None:
        """Normalise les retours en montants négatifs, sans toucher aux quantités."""
        if value is None or type_ticket != "_R_F":
            return value
        return -abs(value)

    @classmethod
    def _parse_ligne_article(
        cls,
        line: str,
        lines: list[str],
        *,
        type_ticket: str,
    ) -> EjLigneTicket:
        """Parse une ligne article, y compris un libellé vide ou une source sur deux lignes."""
        candidate = line
        match = cls._PATTERN_LIGNE_ARTICLE.fullmatch(candidate)

        if match is None:
            second_line = cls._pop_next_line(
                lines,
                error_message=f"Ligne de ticket invalide : {line!r}",
            )
            candidate = f"{line} {second_line}"
            match = cls._PATTERN_LIGNE_ARTICLE.fullmatch(candidate)

        if match is None:
            raise ValueError(f"Ligne de ticket invalide : {candidate!r}")

        libelle = match.group("libelle").strip() or None
        montant = cls._montant_signe(
            parse_money(match.group("montant")),
            type_ticket,
        )
        return EjLigneTicket(
            D_QUANTITE_ARTICLE=int(match.group("quantite")),
            D_LIBELLE_ARTICLE=libelle,
            D_TAUX_TVA_ARTICLE=match.group("taux"),
            D_MONTANT_ARTICLE=montant,
        )

    @staticmethod
    def from_raw_data(*, nom_fichier: str, boutique: str, raw_data: str) -> "EjTicket":
        """Parse le ticket à partir des données brutes et retourne un objet EjTicket."""

        # Initialize the ticket object with default values
        nomFichier: str = nom_fichier
        boutique: str = boutique
        signature: str | None = None
        type: str | None = None
        evenement: str | None = None

        E_NUM_INTERNE: str = ""
        E_DATE_TICKET: date | None = None
        E_HEURE_TICKET: str = ""
        E_NUM_TICKET: str | None = None

        E_HT1: Decimal | None = None
        E_HT2: Decimal | None = None
        E_HT3: Decimal | None = None
        E_HT4: Decimal | None = None

        E_TVA1: Decimal | None = None
        E_TVA2: Decimal | None = None
        E_TVA3: Decimal | None = None
        E_TVA4: Decimal | None = None

        E_HT_NON_TAXABLE: Decimal | None = None

        E_TTC: Decimal | None = None

        E_MDP_CB: Decimal | None = None
        E_MDP_ESPECES: Decimal | None = None
        E_MDP_CHEQUES: Decimal | None = None

        lignes_articles: list[EjLigneTicket] = []

        # Split the raw data into lines and remove any empty lines

        lines = raw_data.splitlines()

        if not lines:
            raise ValueError("Le ticket est vide")

        # Check if the first line is the starting line and remove it if present

        if lines[0].strip().startswith(EjTicket._STARTING_LINE):
            lines.pop(0)

        # Parse the header
        type, E_DATE_TICKET, E_HEURE_TICKET, E_NUM_INTERNE = EjTicket._parse_header(
            lines
        )

        # Parse the remaining lines as ticket lines
        while lines:
            line = lines.pop(0).strip()
            if not line:
                continue

            # Check for starting and ending lines and raise an error if found in the middle of the ticket
            if line.startswith(EjTicket._STARTING_LINE):
                raise ValueError(
                    "Le ticket contient une ligne de démarcation inattendue"
                )

            # Check for the ending line and parse the signature if found
            if line.startswith(EjTicket._ENDING_LINE):
                if signature is not None:
                    raise ValueError("Le ticket contient plusieurs lignes de signature")
                signature = EjTicket._parse_signature(lines)
                break

            # Les autres types ne contiennent pas de lignes de vente,
            # mais leur signature doit tout de même être conservée.
            if type not in {"REG", "_R_F"}:
                continue

            # Reference to the drawer event, if present
            if line.startswith("REF./TIROIR"):
                if evenement is not None:
                    raise ValueError("Le ticket contient plusieurs lignes d'événement")
                evenement = "REF./TIROIR"
                continue

            # Check for the "HORS TAXE" line and parse the TVA code and amount if found
            if line.startswith("HORS TAXE"):
                tokens = line.strip().split()
                if len(tokens) < 4:
                    second_line = EjTicket._pop_next_line(
                        lines,
                        error_message=(
                            f"Ligne de ticket HORS TAXE invalide : {line!r}"
                        ),
                    )
                    tokens += second_line.split()
                if len(tokens) < 4:
                    raise ValueError(f"Ligne de ticket HORS TAXE invalide : {line!r}")

                tva_code = tokens[2]
                montant_str = tokens[3]
                montant = parse_money(montant_str)
                match tva_code:
                    case "1":
                        if E_HT1 is not None:
                            raise ValueError(
                                f"HORS TAXE {tva_code!r} déjà présent dans le ticket"
                            )
                        E_HT1 = montant
                    case "2":
                        if E_HT2 is not None:
                            raise ValueError(
                                f"HORS TAXE {tva_code!r} déjà présent dans le ticket"
                            )
                        E_HT2 = montant
                    case "3":
                        if E_HT3 is not None:
                            raise ValueError(
                                f"HORS TAXE {tva_code!r} déjà présent dans le ticket"
                            )
                        E_HT3 = montant
                    case "4":
                        if E_HT4 is not None:
                            raise ValueError(
                                f"HORS TAXE {tva_code!r} déjà présent dans le ticket"
                            )
                        E_HT4 = montant
                    case _:
                        raise ValueError(
                            f"HORS TAXE {tva_code!r} non géré dans le ticket"
                        )
                continue

            # Check for the "TVA" line and parse the TVA code and amount if found
            if line.startswith("TVA"):
                tokens = line.strip().split()
                if len(tokens) < 3:
                    raise ValueError(f"Ligne de ticket TVA invalide : {line!r}")
                tva_code = tokens[1]
                montant_str = tokens[2]
                montant = parse_money(montant_str)
                match tva_code:
                    case "1":
                        if E_TVA1 is not None:
                            raise ValueError(
                                f"TVA {tva_code!r} déjà présent dans le ticket"
                            )
                        E_TVA1 = montant
                    case "2":
                        if E_TVA2 is not None:
                            raise ValueError(
                                f"TVA {tva_code!r} déjà présent dans le ticket"
                            )
                        E_TVA2 = montant
                    case "3":
                        if E_TVA3 is not None:
                            raise ValueError(
                                f"TVA {tva_code!r} déjà présent dans le ticket"
                            )
                        E_TVA3 = montant
                    case "4":
                        if E_TVA4 is not None:
                            raise ValueError(
                                f"TVA {tva_code!r} déjà présent dans le ticket"
                            )
                        E_TVA4 = montant
                    case _:
                        raise ValueError(f"TVA {tva_code!r} non géré dans le ticket")
                continue

            # Check for the "TOTAL" line and parse the total amount if found
            if line.startswith("TOTAL"):
                tokens = line.strip().split()
                if len(tokens) > 1:
                    montant_str = tokens[1]
                else:
                    montant_str = EjTicket._pop_next_line(
                        lines,
                        error_message=f"Ligne de ticket TOTAL invalide : {line!r}",
                    )
                if E_TTC is not None:
                    raise ValueError(f"TOTAL déjà présent dans le ticket: {line!r}")
                E_TTC = parse_money(montant_str)

            # Check for the "NON TAXABLE" line and parse the non-taxable amount if found
            if line.startswith("NON TAXABLE"):
                tokens = line.strip().split()
                if len(tokens) > 2:
                    montant_str = tokens[2]
                else:
                    montant_str = EjTicket._pop_next_line(
                        lines,
                        error_message=(
                            f"Ligne de ticket NON TAXABLE invalide : {line!r}"
                        ),
                    )
                if E_HT_NON_TAXABLE is not None:
                    raise ValueError(
                        f"NON TAXABLE déjà présent dans le ticket: {line!r}"
                    )
                E_HT_NON_TAXABLE = parse_money(montant_str)

            # Check for the payment method lines and parse the amounts if found
            if line.startswith("CARTES"):
                tokens = line.strip().split()
                if len(tokens) < 2:
                    raise ValueError(f"Ligne de ticket CARTES invalide : {line!r}")
                montant_str = tokens[1]
                if E_MDP_CB is not None:
                    raise ValueError(f"CARTES déjà présent dans le ticket: {line!r}")
                E_MDP_CB = parse_money(montant_str)
                continue

            # Check for the "ESPECES" line and parse the cash amount if found
            if line.startswith("ESPECES"):
                tokens = line.strip().split()
                if len(tokens) < 2:
                    raise ValueError(f"Ligne de ticket ESPECES invalide : {line!r}")
                montant_str = tokens[1]
                if E_MDP_ESPECES is not None:
                    raise ValueError(f"ESPECES déjà présent dans le ticket: {line!r}")
                E_MDP_ESPECES = parse_money(montant_str)
                continue

            # Check for the "CHEQUES" line and parse the check amount if found
            if line.startswith("CHEQUES"):
                tokens = line.strip().split()
                if len(tokens) < 2:
                    raise ValueError(f"Ligne de ticket CHEQUES invalide : {line!r}")
                montant_str = tokens[1]
                if E_MDP_CHEQUES is not None:
                    raise ValueError(f"CHEQUES déjà présent dans le ticket: {line!r}")
                E_MDP_CHEQUES = parse_money(montant_str)
                continue

            # Check for the "FACTURE No." line and parse the ticket number if found
            if line.startswith("FACTURE No."):
                tokens = line.strip().split()
                if len(tokens) < 3:
                    raise ValueError(f"Ligne de ticket FACTURE No. invalide : {line!r}")
                E_NUM_TICKET = tokens[2]
                continue

            if line.startswith("CORRECTION"):
                tokens = line.strip().split()
                if len(tokens) < 2:
                    second_line = EjTicket._pop_next_line(
                        lines,
                        error_message=(
                            f"Ligne de ticket CORRECTION invalide : {line!r}"
                        ),
                    )
                    tokens += second_line.split()
                if len(tokens) < 2:
                    raise ValueError(f"Ligne de ticket CORRECTION invalide : {line!r}")
                montant_str = tokens[1]
                D_CORRECTION = EjTicket._montant_signe(
                    parse_money(montant_str),
                    type,
                )
                ligne_ticket = EjLigneTicket(
                    D_CORRECTION=D_CORRECTION,
                )
                lignes_articles.append(ligne_ticket)

            # Check if the line starts with a digit, indicating a ticket line, and parse it accordingly
            if line[0].isdigit():
                ligne_ticket = EjTicket._parse_ligne_article(
                    line,
                    lines,
                    type_ticket=type,
                )
                lignes_articles.append(ligne_ticket)

        # Les journaux représentent les retours avec des montants imprimés positifs.
        # La base analytique les conserve avec le signe économique attendu.
        E_HT1 = EjTicket._montant_signe(E_HT1, type)
        E_HT2 = EjTicket._montant_signe(E_HT2, type)
        E_HT3 = EjTicket._montant_signe(E_HT3, type)
        E_HT4 = EjTicket._montant_signe(E_HT4, type)
        E_TVA1 = EjTicket._montant_signe(E_TVA1, type)
        E_TVA2 = EjTicket._montant_signe(E_TVA2, type)
        E_TVA3 = EjTicket._montant_signe(E_TVA3, type)
        E_TVA4 = EjTicket._montant_signe(E_TVA4, type)
        E_HT_NON_TAXABLE = EjTicket._montant_signe(E_HT_NON_TAXABLE, type)
        E_TTC = EjTicket._montant_signe(E_TTC, type)
        E_MDP_CB = EjTicket._montant_signe(E_MDP_CB, type)
        E_MDP_ESPECES = EjTicket._montant_signe(E_MDP_ESPECES, type)
        E_MDP_CHEQUES = EjTicket._montant_signe(E_MDP_CHEQUES, type)

        # Create the ticket object
        entete_ticket = EjEnteteTicket(
            nomFichier=nomFichier,
            boutique=boutique,
            signature=signature if signature is not None else None,
            type=type,
            evenement=evenement,
            E_NUM_INTERNE=E_NUM_INTERNE,
            E_DATE_TICKET=E_DATE_TICKET,
            E_HEURE_TICKET=E_HEURE_TICKET,
            E_NUM_TICKET=E_NUM_TICKET,
            E_HT1=E_HT1,
            E_HT2=E_HT2,
            E_HT3=E_HT3,
            E_HT4=E_HT4,
            E_TVA1=E_TVA1,
            E_TVA2=E_TVA2,
            E_TVA3=E_TVA3,
            E_TVA4=E_TVA4,
            E_HT_NON_TAXABLE=E_HT_NON_TAXABLE,
            E_TTC=E_TTC,
            E_MDP_CB=E_MDP_CB,
            E_MDP_ESPECES=E_MDP_ESPECES,
            E_MDP_CHEQUES=E_MDP_CHEQUES,
        )

        ticket = EjTicket(
            entete=entete_ticket,
            lignes_articles=lignes_articles,
        )

        return ticket
