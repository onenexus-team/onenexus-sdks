using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Kiota.Abstractions.Serialization;
using Microsoft.Kiota.Serialization.Json;

namespace OneNexus.Sdk.Core;

/// <summary>
/// Reads every page of a list operation. Each listing pages a private copy of the caller's request,
/// so the caller's object never changes and the same sequence can be enumerated again.
/// </summary>
internal static class Paging
{
    /// <summary>Reads pages until a response has no forward cursor. <paramref name="setCursor"/> runs before every page.</summary>
    internal static async IAsyncEnumerable<TItem> ByCursorAsync<TRequest, TPage, TItem>(
        TRequest request,
        ParsableFactory<TRequest> factory,
        Action<TRequest, string?> setCursor,
        Func<TRequest, CancellationToken, Task<TPage>> readPage,
        Func<TPage, IEnumerable<TItem>?> items,
        Func<TPage, string?> nextCursor,
        [EnumeratorCancellation] CancellationToken cancellationToken)
        where TRequest : IParsable
    {
        TRequest copy = Copy(request, factory);
        var seen = new HashSet<string>(StringComparer.Ordinal);
        string? cursor = null;
        do
        {
            setCursor(copy, cursor);
            TPage page = await readPage(copy, cancellationToken).ConfigureAwait(false);
            foreach (TItem item in items(page) ?? [])
            {
                yield return item;
            }
            cursor = nextCursor(page);
            // A page may hold no items and still have a cursor. A cursor seen before would loop forever.
            if (!string.IsNullOrEmpty(cursor) && !seen.Add(cursor))
            {
                throw new InvalidDataException("The service repeated a pagination cursor.");
            }
        }
        while (!string.IsNullOrEmpty(cursor));
    }

    /// <summary>
    /// Reads pages 1, 2, ... until the reported page count or an empty page. A missing page count ends the listing
    /// after the first page. <paramref name="setPage"/> runs before every page.
    /// </summary>
    internal static async IAsyncEnumerable<TItem> ByPageNumberAsync<TRequest, TPage, TItem>(
        TRequest request,
        ParsableFactory<TRequest> factory,
        Action<TRequest, int> setPage,
        Func<TRequest, CancellationToken, Task<TPage>> readPage,
        Func<TPage, IReadOnlyCollection<TItem>?> items,
        Func<TPage, int?> totalPages,
        [EnumeratorCancellation] CancellationToken cancellationToken)
        where TRequest : IParsable
    {
        TRequest copy = Copy(request, factory);
        for (var number = 1; ; number++)
        {
            setPage(copy, number);
            TPage page = await readPage(copy, cancellationToken).ConfigureAwait(false);
            IReadOnlyCollection<TItem>? rows = items(page);
            if (rows is null || rows.Count == 0)
            {
                yield break;
            }
            foreach (TItem item in rows)
            {
                yield return item;
            }
            if (number >= (totalPages(page) ?? 0))
            {
                yield break;
            }
        }
    }

    private static T Copy<T>(T request, ParsableFactory<T> factory)
        where T : IParsable
    {
        using var writer = new JsonSerializationWriter();
        writer.WriteObjectValue(null, request);
        JsonElement json;
        using (Stream content = writer.GetSerializedContent())
        using (JsonDocument document = JsonDocument.Parse(content))
        {
            json = document.RootElement.Clone();
        }
        return new JsonParseNode(json).GetObjectValue(factory) ?? throw new InvalidDataException("The list request could not be copied.");
    }
}
