"""The zone protocol's ciphers: the client's Blowfish variant and its Huffman table.

These are protocol constants, not secrets: every FINAL FANTASY XI client and server computes
them the same way. The Huffman table itself is read from the player's own game files
(res/compress.dat); no game data is shipped with Fanxi.
"""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

M32 = 0xFFFFFFFF
VIEW_KEY = 0xAD5DE04F
IXFF = b"IXFF"


def md5(data: bytes) -> bytes:
    return hashlib.md5(data).digest()


def _pi_hex_words(count: int) -> list[int]:
    """The first count 32-bit words of pi's fraction: Blowfish's initial P-array and S-boxes."""
    bits = 32 * count + 64
    one = 1 << bits

    def atan_inv(x: int) -> int:
        total, term, x2, n, sign = 0, one // x, x * x, 1, 1
        while term:
            total += sign * (term // n)
            term //= x2
            n += 2
            sign = -sign
        return total

    pi = 16 * atan_inv(5) - 4 * atan_inv(239)
    frac = (pi - 3 * one) >> 64
    return [(frac >> (32 * (count - 1 - i))) & M32 for i in range(count)]


_PI = _pi_hex_words(18 + 1024)


class Blowfish:
    """The client's Blowfish.

    Its round function differs from the standard one: the second and fourth S-box lookups add
    only their lowest bit (plus 32), and nothing is XORed.
    """

    def __init__(self, key16: bytes):
        P = list(_PI[:18])
        S = list(_PI[18:])
        self.P, self.S = P, S
        j = 0
        for i in range(18):
            d = 0
            for _ in range(4):
                b = key16[j]
                if b >= 0x80:  # the key is signed chars: sign extension spills into the word
                    b |= 0xFFFFFF00
                d = ((d << 8) | b) & M32
                j = (j + 1) % len(key16)
            P[i] ^= d
        left = right = 0
        for i in range(0, 18, 2):
            left, right = self.encipher(left, right)
            P[i], P[i + 1] = left, right
        for i in range(0, 1024, 2):
            left, right = self.encipher(left, right)
            S[i], S[i + 1] = left, right

    def _f(self, x: int) -> int:
        S = self.S
        return ((((S[256 + ((x >> 8) & 255)] & 1) ^ 32) + ((S[768 + (x >> 24)] & 1) ^ 32)
                 + S[512 + ((x >> 16) & 255)] + S[x & 255]) & M32)

    def encipher(self, left: int, right: int) -> tuple[int, int]:
        P, f = self.P, self._f
        for i in range(16):
            left ^= P[i]
            right ^= f(left)
            left, right = right, left
        left, right = right, left
        return left ^ P[17], right ^ P[16]

    def decipher(self, left: int, right: int) -> tuple[int, int]:
        P, f = self.P, self._f
        for i in range(17, 1, -1):
            left ^= P[i]
            right ^= f(left)
            left, right = right, left
        left, right = right, left
        return left ^ P[0], right ^ P[1]

    def run(self, buf: bytearray, start: int, words: int, enc: bool) -> None:
        """ECB over an even number of 32-bit words of buf from start, in place."""
        op = self.encipher if enc else self.decipher
        for offset in range(start, start + words * 4, 8):
            left, right = struct.unpack_from("<II", buf, offset)
            struct.pack_into("<II", buf, offset, *op(left, right))


def zone_cipher(key20: bytes) -> Blowfish:
    """The Blowfish for a 20-byte session key: MD5 of it, cut at its first zero byte."""
    digest = bytearray(md5(bytes(key20)))
    if 0 in digest:
        zero = digest.index(0)
        digest[zero:] = bytes(16 - zero)
    return Blowfish(bytes(digest))


class Huffman:
    """The zone protocol's compression: one fixed prefix code per byte, bits LSB first.

    Encoded data is a 1 byte, then the bit stream; its length is the stream's bits + 8.
    """

    def __init__(self, table: bytes):
        if len(table) != 2048:
            raise ValueError("%d bytes, not 2048" % len(table))
        words = struct.unpack("<512I", table)
        self.code = [words[(b + 128) & 255] for b in range(256)]
        self.bits = [words[256 + ((b + 128) & 255)] for b in range(256)]
        self.decode_map = {
            (self.bits[b], self.code[b] & ((1 << self.bits[b]) - 1)): b
            for b in range(256) if self.bits[b] <= 24
        }

    @classmethod
    def from_folder(cls, folder: str | Path) -> "Huffman":
        path = Path(folder) / "compress.dat"
        return cls(path.read_bytes())

    @classmethod
    def from_bytes(cls, table: bytes) -> "Huffman":
        return cls(table)

    def compress(self, data: bytes) -> tuple[bytes, int]:
        acc = n = 0
        out = bytearray([1])
        total = 0
        for b in data:
            k = self.bits[b]
            acc |= (self.code[b] & ((1 << k) - 1)) << n
            n += k
            total += k
            while n >= 8:
                out.append(acc & 255)
                acc >>= 8
                n -= 8
        if n:
            out.append(acc & 255)
        return bytes(out), total + 8

    def decompress(self, data: bytes, nbits: int) -> bytes | None:
        if not data or data[0] != 1:
            return None
        out = bytearray()
        code = length = 0
        limit = min(nbits - 8, (len(data) - 1) * 8)
        for i in range(max(limit, 0)):
            code |= ((data[1 + (i >> 3)] >> (i & 7)) & 1) << length
            length += 1
            b = self.decode_map.get((length, code))
            if b is not None:
                out.append(b)
                code = length = 0
            elif length > 24:
                break
        return bytes(out)


def lobby_packet(command: int, body: bytes, size: int | None = None) -> bytes:
    """A lobby reply: size, "IXFF", command, MD5 of the whole packet (taken with it zeroed), body."""
    n = size if size is not None else 28 + len(body)
    assert 28 + len(body) <= n, "lobby 0x%02X: %d bytes of body in %d" % (command, len(body), n)
    packet = bytearray(n)
    struct.pack_into("<I4sI", packet, 0, n, IXFF, command)
    packet[28:28 + len(body)] = body
    packet[12:28] = md5(bytes(packet))
    return bytes(packet)


def cstr(s: str, n: int) -> bytes:
    b = s.encode("ascii", "replace")[:n - 1]
    return b + bytes(n - len(b))
