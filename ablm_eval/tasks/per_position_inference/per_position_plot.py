from pathlib import Path

import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

__all__ = ["per_pos_compare"]


REGIONS = ["FR1", "CDR1", "FR2", "CDR2", "FR3", "CDR3", "FR4"]


def _extract(df):
    h_loss = []
    l_loss = []
    h_pred = []
    l_pred = []
    h_seq = []
    l_seq = []

    for _, r in df.iterrows():
        hlen = len(r["cdr_mask_heavy"])
        sep = r["separator"]
        seplen = sep.count("<")

        h_loss.append(r["loss"][:hlen])
        l_loss.append(r["loss"][(hlen + seplen) :])
        h_pred.append(r["prediction"][:hlen])
        l_pred.append(r["prediction"][(hlen + seplen) :])
        h_seq.append(r["sequence"].split(sep)[0])
        l_seq.append(r["sequence"].split(sep)[1])

    df["heavy_loss"] = h_loss
    df["light_loss"] = l_loss
    df["heavy_pred"] = h_pred
    df["light_pred"] = l_pred
    df["heavy_sequence"] = h_seq
    df["light_sequence"] = l_seq

    return df


def _region_processing(df):

    data = []
    for _, r in df.iterrows():
        mutated = bool(r["v_mutation_count_aa_heavy"] or r["v_mutation_count_aa_light"])
        model = r["model"]

        # for both chains separately
        for chain in ["heavy", "light"]:
            loss = r[f"{chain}_loss"]
            pred = r[f"{chain}_pred"]
            seq = list(r[f"{chain}_sequence"])
            cdr_mask = r[f"cdr_mask_{chain}"]

            # find regions
            mask_segments = []
            prev_char = cdr_mask[0]
            start_idx = 0

            for i, char in enumerate(cdr_mask):
                if char != prev_char:  # region change
                    mask_segments.append((start_idx, i))
                    start_idx = i
                prev_char = char
            mask_segments.append((start_idx, len(cdr_mask)))  # final region

            # skip any sequences w/o 6 CDRs
            if len(mask_segments) != len(REGIONS):
                continue

            # extract by region
            for region, (start, end) in zip(REGIONS, mask_segments):
                region_loss = loss[start:end]
                region_pred = pred[start:end]
                region_seq = seq[start:end]

                data.append(
                    {
                        "region": region,
                        "model": model,
                        "chain": chain,
                        "mutated": mutated,
                        "loss": region_loss,
                        "mean_loss": np.mean(region_loss),
                        "median_loss": np.median(region_loss),
                        "accuracy": np.mean(
                            [p == t for p, t in zip(region_pred, region_seq)]
                        ),
                    }
                )

    return data


def _per_pos_boxenplot(
    df: pd.DataFrame,
    y_axis: str,
    output_dir: str,
    task_str: str,
    plot_desc: str,
):
    fig, ax = plt.subplots(2, 1, figsize=(8, 6), sharex=True)

    model_order = sorted(df["model"].unique())

    for i, chain in enumerate(["heavy", "light"]):
        # boxplot
        sns.boxenplot(
            data=df[(df["chain"] == chain)],
            x="region",
            y=y_axis,
            hue="model",
            hue_order=model_order,
            dodge=True,
            showfliers=False,
            k_depth="proportion",
            outlier_prop=0.1,
            width=0.7,
            saturation=1,
            ax=ax[i],
        )

        # ticks
        ax[i].tick_params(axis="x", labelsize=11)

        # labels
        ax[i].set_xlabel("")
        ax[i].set_ylabel(
            f"{chain.title()} Chain \n Per-position {y_axis.replace('_', ' ').title()}",
            fontsize=12,
        )

        # remove legends
        ax[i].get_legend().remove()

    # legend
    handles, labels = ax[1].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        fontsize=10,
        title="Model",
    )

    plt.tight_layout()
    plt.savefig(
        f"./{output_dir}/combined-{task_str}-results_{plot_desc}.png",
        bbox_inches="tight",
        dpi=300,
    )


def _summary_df(df):
    # filter for CDR3 only
    cdr3_df = df[(df["region"] == "CDR3") & (df["chain"] ==  "heavy")].drop(columns="mean_loss")

    # group by model, chain, mutated
    means = cdr3_df.groupby(['model', 'mutated']).median(numeric_only=True)
    sems = cdr3_df.groupby(['model', 'mutated']).sem(numeric_only=True)

    # format mean ± sem
    def format_value(mean, sem):
        if pd.notna(sem):
            return f"{mean:.4f} (± {sem:.4f})"
        return f"{mean:.4f}"

    # combine
    combined = pd.DataFrame(index=means.index)
    for col in means.columns:
        combined[f"CDRH3_{col}"] = means[col].combine(sems[col], format_value)

    # make model & mutated columns non-index cols
    combined = combined.reset_index()

    # sort
    combined = combined.sort_values(by=['model', 'mutated'])
    return combined


def per_pos_compare(results_dir, output_dir, task_str, **kwargs):
    # load & concat results
    files = list(Path(results_dir).glob("*.parquet"))
    results = pd.concat([pd.read_parquet(file) for file in files], ignore_index=True)

    # process results
    results = _extract(results)
    data = _region_processing(results)
    data_df = pd.DataFrame(data)

    # plots
    for mutated in [True, False]:
        df = data_df[(data_df["mutated"] == mutated)]
        for metric in ["median_loss", "accuracy"]:
            _per_pos_boxenplot(
                df,
                y_axis=metric,
                output_dir=output_dir,
                task_str=task_str,
                plot_desc=f"{'mutated' if mutated else 'unmutated'}_{metric}",
            )

    summary_df = _summary_df(data_df)
    summary_df.to_csv(f"{output_dir}/results-summary_{task_str}.csv", index=False)
